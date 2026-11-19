"""Tests for revision 4 of the reader panel spec (docs/specs/reader-panel.md). All data here is invented.

This module covers what revision 4 adds to the plan file and the freeze file (who wrote each
anchor, the anchor's note, the lens's disclosure and criteria, the prompt in each form and the
refusal of a plan frozen under an earlier revision). No test here starts a live reader: every
reader is the built-in fake reader.
"""

import hashlib
import itertools
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import panel  # noqa: E402
from tests.test_ab import Setup as AbSetup  # noqa: E402
from tests.test_panel import Setup, ANCHORS, LENSES, RANK, SIX_PASS  # noqa: E402

PROMPT_SHA256_REVISION_3 = "79657b05dbea178a019140c4f8bba1fddd1eba4c044d2b191f07dd849579ae1c"
ABC_LENS = "recruiter | recruiter.lens.txt | author-edited-version no | criteria a,b,c"
EARLIER = ("frozen under an earlier revision: plan.txt.freeze; score it with the release that "
           "froze it, or rewrite it as a new plan")
WRITTEN_BY = ("written-by is user, third-party, unknown or model <family>, with more models as "
              "a comma list: %s")


class Refusals(unittest.TestCase):
    def assertRefused(self, s, line_text, message):
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(result.ran)
        self.assertIn("plan line %d: %s" % (s.line_of(line_text), message),
                      result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))


class WrittenByCase(Refusals):
    def test_10_50_written_by_is_required(self):
        s = Setup(self, anchors=["strong | anchor-strong.txt", ANCHORS[1]])
        self.assertRefused(s, "strong |", "an anchor needs written-by (revision 4): strong")
        s = Setup(self, anchors=[ANCHORS[0], "weak | anchor-weak.txt | written-by model"])
        self.assertRefused(s, "weak |", WRITTEN_BY % "written-by model")
        model = ["strong | anchor-strong.txt | written-by model fam-a, model fam-b | note "
                 "edited from a template", ANCHORS[1]]
        s = Setup(self, anchors=model, fake_reader=RANK)
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertIn("anchor strong: written by model fam-a, model fam-b; note: edited from a "
                      "template", s.result_lines())
        self.assertIn("anchor weak: written by user", s.result_lines())

    def test_each_form_of_who_is_kept(self):
        for who, stored in (("user", "user"), ("third-party", "third-party"),
                            ("unknown", "unknown"), ("model fam-a", "model fam-a"),
                            ("model fam-a, model fam-b", "model fam-a, model fam-b")):
            with self.subTest(who):
                s = Setup(self, anchors=["strong | anchor-strong.txt | written-by " + who,
                                         ANCHORS[1]])
                self.assertEqual(s.freeze().exit_code, 0)
                self.assertEqual(s.plan.written_by["strong"], stored)

    def test_a_family_is_lower_cased_and_kept_once(self):
        s = Setup(self, anchors=["strong | anchor-strong.txt | written-by model fam-a, model "
                                 "FAM-A, model Fam-B", ANCHORS[1]])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.plan.written_by["strong"], "model fam-a, model fam-b")

    def test_a_third_field_that_is_not_a_form_is_refused_naming_its_line(self):
        for text in ("written-by", "written-by nobody", "written-by model a b",
                     "written-by model fam-a; model fam-b", "written-by user, model a",
                     "note a note", "wrote user"):
            with self.subTest(text):
                s = Setup(self, anchors=["strong | anchor-strong.txt | " + text, ANCHORS[1]])
                self.assertRefused(s, "strong |", WRITTEN_BY % text)

    def test_a_note_holds_the_rest_of_the_line_with_its_separators(self):
        line = "strong | anchor-strong.txt | written-by user | note edited | by hand | twice"
        s = Setup(self, anchors=[line, ANCHORS[1]], fake_reader=RANK)
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertEqual(s.plan.notes, {"strong": "edited | by hand | twice"})
        self.assertIn("anchor strong: written by user; note: edited | by hand | twice",
                      s.result_lines())
        # An empty piece inside a note is part of its text, not an empty field.
        inside = "strong | anchor-strong.txt | written-by user | note a |  | b"
        t = Setup(self, anchors=[inside, ANCHORS[1]])
        self.assertEqual(t.freeze().exit_code, 0)
        self.assertIn(" | ", t.plan.notes["strong"])

    def test_a_note_without_text_or_not_last_is_refused(self):
        s = Setup(self, anchors=["strong | anchor-strong.txt | written-by user | note",
                                 ANCHORS[1]])
        self.assertRefused(s, "strong |", "a note needs text: strong")
        s = Setup(self, anchors=[ANCHORS[0], "weak | anchor-weak.txt | written-by user | "
                                 "comment text"])
        self.assertRefused(s, "weak |", "an anchor's last field may be note <text>: "
                           "comment text")

    def test_an_empty_field_or_a_bad_name_keeps_revision_3s_message(self):
        s = Setup(self, anchors=["strong | anchor-strong.txt |  | written-by user", ANCHORS[1]])
        self.assertRefused(s, "strong |", "an empty field")
        s = Setup(self, anchors=[ANCHORS[0], "middling | x.txt | written-by user"])
        self.assertRefused(s, "middling",
                           "an anchor is written: strong | file, or weak | file")
        s = Setup(self, anchors=[ANCHORS[0], "weak"])
        self.assertRefused(s, "weak", "an anchor is written: strong | file, or weak | file")


class LensFieldsCase(Refusals):
    def test_10_58_the_author_edited_disclosure(self):
        s = Setup(self, lenses=["recruiter | recruiter.lens.txt", LENSES[1]])
        self.assertRefused(s, "recruiter |", "a lens needs author-edited-version yes or no "
                           "(revision 4): recruiter")
        plans = {}
        for answer in ("no", "yes"):
            lenses = ["recruiter | recruiter.lens.txt | author-edited-version " + answer,
                      LENSES[1]]
            s = Setup(self, lenses=lenses, fake_reader=RANK,
                      rules=["recruiter | " + SIX_PASS])
            self.assertEqual(s.frozen_run().exit_code, 0)
            plans[answer] = s.result_lines()
            self.assertIn("l1 author edited the version: " + answer, plans[answer])
            self.assertIn("l2 author edited the version: no", plans[answer])
        verdicts = {}
        for answer, lines in plans.items():
            verdicts[answer] = [x for x in lines if " verdict: " in x]
        self.assertEqual(verdicts["yes"], verdicts["no"])
        self.assertTrue(verdicts["no"])

    def test_the_disclosure_line_follows_its_lens(self):
        s = Setup(self, fake_reader=RANK)
        self.assertEqual(s.frozen_run().exit_code, 0)
        lines = s.result_lines()
        for arm in ("l1", "l2"):
            at = [i for i, x in enumerate(lines) if x.startswith("lens %s: " % arm)][0]
            self.assertEqual(lines[at + 1], "%s author edited the version: no" % arm)

    def test_the_extra_fields_come_in_any_order_each_once(self):
        for extras in ("max 10 | author-edited-version yes | criteria a,b",
                       "criteria a,b | max 10 | author-edited-version yes",
                       "author-edited-version yes | criteria a,b | max 10"):
            with self.subTest(extras):
                s = Setup(self, lenses=["recruiter | recruiter.lens.txt | " + extras,
                                        LENSES[1]])
                self.assertEqual(s.freeze().exit_code, 0)
                lens = s.plan.lenses[0]
                self.assertEqual((lens.max, lens.author_edited, lens.criteria),
                                 (10, "yes", ("a", "b")))

    def test_a_repeated_or_other_extra_field_is_refused(self):
        message = ("a lens's extra fields may be max <n>, author-edited-version yes or no, and "
                   "criteria <names>, each at most once: %s")
        for extra in ("author-edited-version no", "criteria a", "max 9", "colour red",
                      "author-edited-version maybe"):
            with self.subTest(extra):
                base = ["recruiter | recruiter.lens.txt | author-edited-version no | "
                        "criteria b | max 8"]
                s = Setup(self, lenses=[base[0] + " | " + extra, LENSES[1]])
                self.assertRefused(s, "recruiter |", message % extra)

    def test_criteria_are_names_each_once(self):
        message = "criteria are names of letters, digits and -, separated by commas, each once: %s"
        for text in ("a,a", "a,,b", "a b", "a,b,", "ä"):
            with self.subTest(text):
                s = Setup(self, lenses=["recruiter | recruiter.lens.txt | "
                                        "author-edited-version no | criteria " + text,
                                        LENSES[1]])
                self.assertRefused(s, "criteria", message % text)
        s = Setup(self, lenses=["recruiter | recruiter.lens.txt | author-edited-version no | "
                                "criteria a, b-1 ,C", LENSES[1]])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.plan.lenses[0].criteria, ("a", "b-1", "C"))

    def test_a_criterion_field_in_a_fake_rule_names_a_lens_that_has_it(self):
        lenses = [ABC_LENS, LENSES[1]]
        for rule in ('recruiter | write "2" in CRITERION-a', "recruiter | omit CRITERION-b"):
            with self.subTest(rule):
                s = Setup(self, lenses=lenses, fake_reader=[rule])
                self.assertEqual(s.freeze().exit_code, 0)
        for rule, field in (('write "2" in CRITERION-a', "CRITERION-a"),
                            ('all | write "2" in CRITERION-a', "CRITERION-a"),
                            ('manager | write "2" in CRITERION-a', "CRITERION-a"),
                            ('recruiter | write "2" in CRITERION-z', "CRITERION-z"),
                            ("recruiter | omit CRITERION-", "CRITERION-")):
            with self.subTest(rule):
                s = Setup(self, lenses=lenses, fake_reader=[rule])
                self.assertRefused(s, "CRITERION", "not a reply field: " + field)

    def test_a_plan_rule_cannot_test_a_criterion_field(self):
        s = Setup(self, lenses=[ABC_LENS, LENSES[1]],
                  rules=["recruiter | PASS if CRITERION-a flagged in 1 or more; otherwise "
                         "INCONCLUSIVE"])
        self.assertRefused(s, "CRITERION-a",
                           "not a reply field a rule can test: CRITERION-a")


class PlanKeysCase(Refusals):
    def test_the_default_is_two_anchor_reads_per_reader(self):
        s = Setup(self, anchor_reads_per_reader=None)
        self.assertEqual(s.plan.anchor_reads_per_reader, 2)
        self.assertEqual(s.plan.reads_per_lens(), 14)
        t = Setup(self, anchor_reads_per_reader="1")
        self.assertEqual(t.plan.anchor_reads_per_reader, 1)

    def test_the_new_scalar_keys_are_kept(self):
        s = Setup(self, calibration="../c/plan.txt.freeze")
        self.assertEqual(s.plan.calibration, "../c/plan.txt.freeze")
        t = Setup(self, extends="../first/plan.txt.freeze")
        self.assertEqual(t.plan.extends, "../first/plan.txt.freeze")
        u = Setup(self)
        self.assertEqual((u.plan.calibration, u.plan.extends, u.plan.calibration_only),
                         (None, None, False))

    def test_calibration_only_is_yes_or_left_out(self):
        s = Setup(self, calibration_only="no", rules=None)
        self.assertRefused(s, "calibration-only", "calibration-only is yes, or left out")
        t = Setup(self, calibration_only="yes", rules=None)
        self.assertTrue(t.plan.calibration_only)

    def test_a_calibration_only_plan_takes_no_rules_and_no_other_runs(self):
        s = Setup(self, calibration_only="yes", rules=["recruiter | " + SIX_PASS])
        self.assertRefused(s, "recruiter | PASS",
                           "a calibration-only plan reads no version, so it takes no rules")
        for key in ("calibration", "extends", "replicate_of"):
            with self.subTest(key):
                s = Setup(self, calibration_only="yes", **{key: "../x/plan.txt.freeze"})
                self.assertRefused(s, "calibration-only", "a calibration-only plan may not "
                                   "carry calibration, extends or replicate-of")

    def test_extends_does_not_go_with_amends_or_replicate_of(self):
        for key in ("amends", "replicate_of"):
            with self.subTest(key):
                s = Setup(self, extends="../x/plan.txt.freeze", **{key: "../y/plan.txt.freeze"})
                self.assertRefused(s, "extends", "a plan may not carry extends with amends or "
                                   "replicate-of")


class PromptFormsCase(unittest.TestCase):
    def test_10_52_the_prompt_changes_only_for_a_lens_with_criteria(self):
        self.assertEqual(panel.prompt_sha256(), PROMPT_SHA256_REVISION_3)
        s = Setup(self, fake_reader=RANK)
        self.assertEqual(s.frozen_run().exit_code, 0)
        freeze = s.read("plan.txt.freeze").splitlines()
        self.assertEqual([x for x in freeze if "PROMPT.txt" in x],
                         ["%s  PROMPT.txt (built into the tool)" % PROMPT_SHA256_REVISION_3])
        self.assertEqual([x for x in s.result_lines() if x.startswith("prompt sha256")],
                         ["prompt sha256: " + PROMPT_SHA256_REVISION_3])
        for arm in ("l1", "l2"):
            self.assertEqual(s.read(panel.READS_DIR, arm, "1", "PROMPT.txt"), panel.PROMPT)
        # A lens with criteria is read with its own form; the other lens keeps the first.
        t = Setup(self, lenses=[ABC_LENS, LENSES[1]],
                  fake_reader=RANK + ['recruiter | write "2" in CRITERION-a',
                                      'recruiter | write "1" in CRITERION-b',
                                      'recruiter | write "2" in CRITERION-c'])
        self.assertEqual(t.freeze().exit_code, 0)
        form = panel.criteria_prompt(("a", "b", "c"))
        digest = sha256_text(form)
        self.assertNotEqual(digest, PROMPT_SHA256_REVISION_3)
        freeze = t.read("plan.txt.freeze").splitlines()
        at = freeze.index("%s  PROMPT.txt (built into the tool)" % PROMPT_SHA256_REVISION_3)
        self.assertEqual(freeze[at + 1],
                         "%s  PROMPT.txt (built into the tool, criteria a,b,c)" % digest)
        self.assertEqual(t.run().exit_code, 0)
        self.assertEqual(t.read(panel.READS_DIR, "l1", "1", "PROMPT.txt"), form)
        self.assertEqual(t.read(panel.READS_DIR, "l2", "1", "PROMPT.txt"), panel.PROMPT)

    def test_the_criteria_prompt_is_this_text(self):
        expected = PROMPT_ABC
        self.assertEqual(panel.criteria_prompt(("a", "b", "c")), expected)
        self.assertEqual(sha256_text(expected), sha256_text(panel.prompt_of(("a", "b", "c"))))
        self.assertIs(panel.prompt_of(()), panel.PROMPT)
        self.assertNotIn("SCORE", panel.criteria_prompt(("a",)))
        self.assertEqual(panel.criteria_prompt(("a", "b")).count("CRITERION-"), 2)

    def test_each_distinct_list_adds_one_form_in_lens_order(self):
        lenses = [ABC_LENS,
                  "manager | hiring-manager.lens.txt | author-edited-version no | criteria "
                  "z,y",
                  "third | third.txt | author-edited-version no | criteria a,b,c"]
        s = Setup(self, lenses=lenses)
        s.write("third.txt", "Your role: a peer.\n")
        self.assertEqual(s.freeze().exit_code, 0)
        labels = [x.split("  ", 1)[1] for x in s.read("plan.txt.freeze").splitlines()
                  if "PROMPT.txt" in x]
        self.assertEqual(labels, ["PROMPT.txt (built into the tool)",
                                  "PROMPT.txt (built into the tool, criteria a,b,c)",
                                  "PROMPT.txt (built into the tool, criteria z,y)"])

    def test_a_changed_form_stops_the_run(self):
        s = Setup(self, lenses=[ABC_LENS, LENSES[1]])
        self.assertEqual(s.freeze().exit_code, 0)
        real = panel.criteria_prompt
        panel.criteria_prompt = lambda criteria: real(criteria) + "One more line.\n"
        self.addCleanup(setattr, panel, "criteria_prompt", real)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "changed since the freeze: PROMPT.txt (built into the tool, criteria a,b,c)"])
        self.assertFalse(s.exists(panel.READS_DIR))


class RevisionRecordCase(unittest.TestCase):
    def run_plan(self):
        s = Setup(self, fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        self.assertEqual(s.frozen_run().exit_code, 0)
        return s

    def test_10_62_a_plan_frozen_under_an_earlier_revision_is_refused(self):
        s = self.run_plan()
        freeze = s.read("plan.txt.freeze").splitlines()
        self.assertEqual(freeze[-1], "revision: 4")
        self.assertEqual(freeze.count("revision: 4"), 1)
        for name, replace in (("revision 3", lambda text: text.replace("revision: 4",
                                                                       "revision: 3")),
                              ("no revision", lambda text: text.replace("revision: 4\n", "")),
                              ("revision 4 twice", lambda text: text + "revision: 4\n"),
                              ("revision 40", lambda text: text.replace("revision: 4",
                                                                        "revision: 40"))):
            with self.subTest(name):
                t = Setup(self, fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
                self.assertEqual(t.freeze().exit_code, 0)
                t.edit("plan.txt.freeze", replace)
                before = t.tree_hashes()
                ran = t.run()
                self.assertEqual((ran.exit_code, ran.error), (2, EARLIER))
                self.assertEqual(t.tree_hashes(), before)
                self.assertEqual(t.result_names(), [])
        # score, on a run made before the record was changed
        s.edit("plan.txt.freeze", lambda text: text.replace("revision: 4\n", ""))
        before = s.tree_hashes()
        scored = s.score()
        self.assertEqual((scored.exit_code, scored.error), (2, EARLIER))
        self.assertEqual(s.tree_hashes(), before)
        self.assertEqual(s.result_names(), ["result-1.txt"])

    def test_a_missing_freeze_file_keeps_revision_3s_message(self):
        s = Setup(self, fake_reader=RANK)
        for call in (s.run, s.score):
            result = call()
            self.assertEqual(result.exit_code, 2)
            self.assertEqual(result.error.splitlines(), ["no freeze file: plan.txt.freeze"])

    def test_the_record_comes_after_every_hash_line(self):
        s = Setup(self, lenses=[ABC_LENS, LENSES[1]])
        self.assertEqual(s.freeze().exit_code, 0)
        lines = s.read("plan.txt.freeze").splitlines()
        self.assertEqual(lines[-1], "revision: 4")
        self.assertTrue(all("  " in x for x in lines[:-1]))

    def test_a_replicate_of_an_earlier_revision_is_refused_at_freeze(self):
        first = Setup(self, fake_reader=RANK)
        self.assertEqual(first.freeze().exit_code, 0)
        first.edit("plan.txt.freeze", lambda text: text.replace("revision: 4\n", ""))
        second = Setup(self, fake_reader=RANK,
                       replicate_of=os.path.join("..", os.path.basename(first.folder),
                                                 "plan.txt.freeze"))
        result = second.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("frozen under an earlier revision: %s"
                      % os.path.join("..", os.path.basename(first.folder), "plan.txt.freeze"),
                      result.error.splitlines())
        self.assertFalse(second.exists("plan.txt.freeze"))


class SharedHarnessCase(unittest.TestCase):
    def test_an_ab_freeze_holds_no_revision_line_and_no_form(self):
        a = AbSetup(self)
        self.assertEqual(a.freeze().exit_code, 0)
        lines = a.read("plan.txt.freeze").splitlines()
        self.assertEqual([x for x in lines if x.startswith("revision")], [])
        self.assertEqual([x for x in lines if "criteria" in x], [])
        self.assertTrue(all("  " in x for x in lines))

    def test_the_new_harness_parameters_default_to_nothing(self):
        s = Setup(self)
        result = panel.harness.freeze(s.plan_path, panel.parse, panel._inputs,
                                      panel.prompt_sha256())
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertEqual(s.read("plan.txt.freeze").splitlines()[-1],
                         "%s  %s" % (panel.prompt_sha256(), panel.PROMPT_LABEL))


HEADROOM_RULE = "recruiter | PASS if score at least 6 in 6 of 6; otherwise INCONCLUSIVE"
FLAGGED_RULE = ("recruiter | FAIL if DOUBTS flagged in 3 or more; PASS if score at least 7 in "
                "6 of 6; otherwise INCONCLUSIVE")
OVERALL_12 = "overall | PASS if score at least 7 in 12 of 12; otherwise INCONCLUSIVE"
FIVE_OF_SIX = "recruiter | PASS if score at least 7 in 5 of 6; otherwise INCONCLUSIVE"
TAG = " [not blind: 0 reads left out] [uncalibrated]"
NO_HEADROOM_9 = "no headroom (strong anchor median 9, version median 9)"
VERSION_9 = ["recruiter | strong | score 9", "recruiter | weak | score 2",
             "recruiter | version | score 9",
             "manager | strong | score 8", "manager | weak | score 3",
             "manager | version | score 7"]
BOTH_9 = [x.replace("manager | strong | score 8", "manager | strong | score 9")
          .replace("manager | version | score 7", "manager | version | score 9")
          for x in VERSION_9]
ABC = ['recruiter | write "2" in CRITERION-a', 'recruiter | write "1" in CRITERION-b',
       'recruiter | write "2" in CRITERION-c']
FEW = "headroom not assessed (%d valid strong-anchor reads, at least 3 needed)"


class Run(unittest.TestCase):
    def done(self, **overrides):
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()


class HeadroomCase(Run):
    def test_10_45_headroom_line_with_room(self):
        _s, result, lines = self.done(
            fake_reader=[x.replace("recruiter | version | score 7", "recruiter | version | "
                                   "score 6") for x in RANK], rules=[HEADROOM_RULE])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("headroom l1: strong anchor median 9, version median 6", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        self.assertEqual([x for x in lines if "headroom l1: none" in x or " reason: " in x], [])

    def test_10_46_no_headroom_makes_a_higher_score_pass_inconclusive(self):
        _s, result, lines = self.done(fake_reader=VERSION_9, rules=["recruiter | " + SIX_PASS])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("rule r1 (l1) count: score at least 7: 6 of 6 valid reads", lines)
        self.assertIn("headroom l1: strong anchor median 9, version median 9", lines)
        self.assertIn("headroom l1: none; next step: a criterion rubric", lines)
        self.assertIn("rule r1 (l1) reason: " + NO_HEADROOM_9, lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, lines)
        # The manager's strong anchor median is 8, above its version's 7: it has room.
        self.assertIn("headroom l2: strong anchor median 8, version median 7", lines)
        self.assertEqual([x for x in lines if x.startswith("headroom l2: none")], [])

    def test_10_47_headroom_leaves_a_fail_alone(self):
        _s, _result, lines = self.done(
            fake_reader=VERSION_9 + ['recruiter | version | write "too long" in DOUBTS'],
            rules=[FLAGGED_RULE])
        self.assertIn("rule r1 (l1) verdict: FAIL" + TAG, lines)
        self.assertEqual([x for x in lines if x.startswith("rule r1 (l1) reason")], [])
        self.assertIn("headroom l1: strong anchor median 9, version median 9", lines)
        self.assertIn("headroom l1: none; next step: a criterion rubric", lines)

    def test_10_48_too_few_strong_anchor_reads_leave_headroom_not_assessed(self):
        _s, _result, lines = self.done(fake_reader=RANK, anchor_reads_per_reader="1",
                                       rules=["recruiter | " + SIX_PASS])
        for arm in ("l1", "l2"):
            self.assertIn("headroom %s: not assessed (2 valid strong-anchor reads, at least 3 "
                          "needed)" % arm, lines)
        self.assertIn("rule r1 (l1) reason: " + FEW % 2, lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, lines)
        # The default, 2 anchor reads per reader, gives each lens 4 and 10.1's rule passes.
        _s, _result, lines = self.done(fake_reader=RANK, rules=["recruiter | " + SIX_PASS])
        self.assertIn("headroom l1: strong anchor median 9, version median 7", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        # One reader: 2 strong reads at the default, 3 at anchor-reads-per-reader 3.
        one = dict(readers=["r1 | fake"], fake_reader=RANK[:3], lenses=LENSES[:1],
                   rules=["recruiter | PASS if score at least 7 in 3 of 3; otherwise "
                          "INCONCLUSIVE"])
        _s, _result, lines = self.done(**one)
        self.assertIn("headroom l1: not assessed (2 valid strong-anchor reads, at least 3 "
                      "needed)", lines)
        _s, _result, lines = self.done(anchor_reads_per_reader="3", **one)
        self.assertIn("headroom l1: strong anchor median 9, version median 7", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)

    def test_10_49_an_overall_rule_needs_headroom_on_every_counted_lens(self):
        _s, _result, lines = self.done(fake_reader=RANK + ["manager | version | score 9"],
                                       rules=[OVERALL_12])
        self.assertIn("rule r1 (overall) count: score at least 7: 12 of 12 valid reads", lines)
        self.assertIn("rule r1 (overall) reason: no headroom on l2", lines)
        self.assertIn("rule r1 (overall) verdict: INCONCLUSIVE" + TAG, lines)
        _s, _result, lines = self.done(fake_reader=RANK, anchor_reads_per_reader="1",
                                       rules=[OVERALL_12])
        self.assertIn("rule r1 (overall) reason: headroom not assessed on l1, l2", lines)
        self.assertIn("rule r1 (overall) verdict: INCONCLUSIVE" + TAG, lines)

    def test_an_overall_reason_names_both_kinds_in_plan_order(self):
        # l1 has no valid read of the version; l2 has no headroom. The overall rule counts l2's
        # reads, passes by a score clause, and names each lens under its own part.
        rules = ["overall | PASS if score at least 7 in 0 or more; otherwise INCONCLUSIVE"]
        _s, _result, lines = self.done(
            fake_reader=RANK + ["manager | version | score 9", "recruiter | version | omit SCORE"],
            rules=rules)
        self.assertIn("headroom l1: not assessed (no valid version read)", lines)
        self.assertIn("rule r1 (overall) reason: no headroom on l2; headroom not assessed on "
                      "l1", lines)
        self.assertIn("rule r1 (overall) verdict: INCONCLUSIVE" + TAG, lines)

    def test_a_lens_with_strong_reads_and_no_valid_version_read_is_not_assessed(self):
        rules = ["recruiter | PASS if score at least 7 in 0 or more; otherwise INCONCLUSIVE"]
        _s, result, lines = self.done(fake_reader=RANK + ["recruiter | version | omit SCORE"],
                                      rules=rules)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("headroom l1: not assessed (no valid version read)", lines)
        self.assertIn("rule r1 (l1) reason: headroom not assessed (no valid version read)",
                      lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, lines)

    def test_a_higher_score_clause_only_is_touched(self):
        # A PASS through a flagged-field clause stays PASS when there is no headroom.
        rule = "recruiter | PASS if DOUBTS not flagged in 6 of 6; otherwise INCONCLUSIVE"
        _s, _result, lines = self.done(fake_reader=VERSION_9, rules=[rule])
        self.assertIn("headroom l1: none; next step: a criterion rubric", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        self.assertEqual([x for x in lines if x.startswith("rule r1 (l1) reason")], [])
        # A FAIL by a score clause and an INCONCLUSIVE are left alone too.
        low = "recruiter | FAIL if score at least 9 in 6 of 6; otherwise INCONCLUSIVE"
        _s, _result, lines = self.done(fake_reader=VERSION_9, rules=[low])
        self.assertIn("rule r1 (l1) verdict: FAIL" + TAG, lines)
        self.assertEqual([x for x in lines if x.startswith("rule r1 (l1) reason")], [])
        never = "recruiter | PASS if score at least 7 in 7 of 7; otherwise INCONCLUSIVE"
        _s, _result, lines = self.done(fake_reader=VERSION_9, rules=[never])
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, lines)
        self.assertEqual([x for x in lines if x.startswith("rule r1 (l1) reason")], [])

    def test_a_not_blind_readers_anchor_reads_are_not_in_the_median(self):
        # Three readers, three anchor reads each, the last two not blind and scoring the strong
        # anchor 2: the median is over reader 1's three reads, 9, whatever theirs are.
        low = ["recruiter | strong | score 2 | read %d" % n for n in range(4, 10)]
        _s, result, lines = self.done(
            readers=["r1 | fake", "r2 | fake | not-blind", "r3 | fake | not-blind"],
            anchor_reads_per_reader="3", fake_reader=RANK[:3] + low, lenses=LENSES[:1],
            rules=["recruiter | PASS if score at least 7 in 3 or more; otherwise INCONCLUSIVE"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("headroom l1: strong anchor median 9, version median 7", lines)
        self.assertIn("rule r1 (l1) verdict: PASS [not blind: 6 reads left out] [uncalibrated]",
                      lines)

    def test_10_63_an_even_median_is_the_mean_of_the_two_middle_values(self):
        seven = ["recruiter | strong | score 7", "recruiter | weak | score 2",
                 "recruiter | version | score 7", "manager | strong | score 8",
                 "manager | weak | score 3", "manager | version | score 7"]
        halves = ["recruiter | strong | score 8 | read 3", "recruiter | strong | score 8 | read 4"]
        _s, _result, lines = self.done(fake_reader=seven + halves,
                                       rules=["recruiter | " + SIX_PASS])
        self.assertIn("headroom l1: strong anchor median 7.5, version median 7", lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        _s, _result, lines = self.done(fake_reader=seven, rules=["recruiter | " + SIX_PASS])
        self.assertIn("headroom l1: strong anchor median 7, version median 7", lines)
        self.assertIn("headroom l1: none; next step: a criterion rubric", lines)
        self.assertIn("rule r1 (l1) reason: no headroom (strong anchor median 7, version "
                      "median 7)", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, lines)

    def test_medians_are_whole_or_end_in_half(self):
        for scores, doubled, text in (([7], 14, "7"), ([1, 2], 3, "1.5"), ([-3, -2], -5, "-2.5"),
                                      ([0, 1], 1, "0.5"), ([-1, 0], -1, "-0.5"),
                                      ([5, 1, 3], 6, "3"), ([4, 1, 3, 2], 5, "2.5")):
            with self.subTest(scores=scores):
                self.assertEqual(panel.doubled_median(scores), doubled)
                self.assertEqual(panel.median_text(doubled), text)

    def test_10_64_headroom_applies_to_a_lifted_verdict(self):
        rules = VERSION_9 + ["recruiter | version | omit SCORE | read 9"]
        _s, result, lines = self.done(fake_reader=rules, rules=[FIVE_OF_SIX],
                                      min_valid_reads="5")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("rule r1 (l1) completions (missing reads: 1): settled: PASS", lines)
        self.assertIn("rule r1 (l1) verdict: INCONCLUSIVE" + TAG, lines)
        self.assertIn("rule r1 (l1) reason: " + NO_HEADROOM_9, lines)
        self.assertEqual([x for x in lines if "lifted from" in x], [])
        # With room, the lift stands, and its reason is the one printed.
        rules = RANK + ["recruiter | version | omit SCORE | read 9"]
        _s, _result, lines = self.done(fake_reader=rules, rules=[FIVE_OF_SIX],
                                       min_valid_reads="5")
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        self.assertIn("rule r1 (l1) reason: lifted from INCONCLUSIVE: settled under every "
                      "completion of 1 missing reads; read floor 5 met", lines)

    def test_headroom_lines_only_for_counted_lenses(self):
        _s, _result, lines = self.done(
            fake_reader=RANK[:3] + ["manager | score 5"], rules=["recruiter | " + SIX_PASS,
                                                                  "manager | " + SIX_PASS])
        self.assertTrue([x for x in lines if x.startswith("headroom l1:")])
        self.assertEqual([x for x in lines if x.startswith("headroom l2:")], [])
        # A rule on the uncounted lens keeps its gate reason and gets no headroom reason.
        self.assertIn("rule r2 (l2) reason: the anchor gate failed on l2", lines)
        self.assertEqual([x for x in lines if x.startswith("rule r2 (l2) reason")
                          and "headroom" in x], [])

    def test_headroom_line_comes_after_the_lens_s_score_lines(self):
        _s, _result, lines = self.done(fake_reader=VERSION_9)
        at = lines.index("headroom l1: strong anchor median 9, version median 9")
        self.assertEqual(lines[at + 1], "headroom l1: none; next step: a criterion rubric")
        self.assertTrue(lines[at - 1].startswith("scores l1"))
        self.assertTrue(lines[at + 2].startswith("reads l2 strong"))


class CriteriaCase(Run):
    def test_10_51_criteria_are_summed_by_the_tool(self):
        lenses = [ABC_LENS, LENSES[1]]
        _s, result, lines = self.done(lenses=lenses, fake_reader=ABC)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("scores l1 version: scores=6 total=30 mean=5.00 lowest=5 highest=5",
                      lines)
        self.assertIn("criteria l1: 14 replies carried a SCORE field, not read", lines)
        self.assertEqual([x for x in lines if x.startswith("criteria l2")], [])
        _s, _result, lines = self.done(lenses=lenses, fake_reader=ABC + ["recruiter | omit "
                                                                         "SCORE"])
        self.assertIn("scores l1 version: scores=6 total=30 mean=5.00 lowest=5 highest=5",
                      lines)
        self.assertIn("criteria l1: 0 replies carried a SCORE field, not read", lines)
        for rule, reason in (("recruiter | omit CRITERION-b | read 9", "missing CRITERION-b"),
                             ('recruiter | write "two" in CRITERION-a | read 9',
                              "CRITERION-a is not an integer")):
            with self.subTest(rule):
                _s, result, lines = self.done(lenses=lenses, fake_reader=ABC + [rule])
                self.assertEqual(result.exit_code, 1)
                self.assertIn("read l1/9: reader=r1 document=version FAILED (%s)" % reason,
                              lines)
                self.assertIn("scores l1 version: scores=5 total=25 mean=5.00 lowest=5 "
                              "highest=5", lines)
                # The failed reply still carried a SCORE field: 14 replies.
                self.assertIn("criteria l1: 14 replies carried a SCORE field, not read", lines)

    def test_the_sum_is_the_score_whatever_score_says(self):
        # Every criterion 3, SCORE 5 (the fake default): the read scores 9, not 5.
        threes = ['recruiter | write "3" in CRITERION-%s' % name for name in "abc"]
        _s, _result, lines = self.done(lenses=[ABC_LENS, LENSES[1]], fake_reader=threes)
        self.assertIn("scores l1 version: scores=6 total=54 mean=9.00 lowest=9 highest=9", lines)
        self.assertIn("anchor gate l1: failed (weak read l1/5 scored 9, above 4; weak read "
                      "l1/6 scored 9, above 4; weak read l1/7 scored 9, above 4; weak read "
                      "l1/8 scored 9, above 4)", lines)

    def test_a_not_run_or_absent_reply_is_not_counted(self):
        _s, _result, lines = self.done(lenses=[ABC_LENS, LENSES[1]], fake_reader=ABC,
                                       spend_ceiling="10")
        self.assertIn("criteria l1: 10 replies carried a SCORE field, not read", lines)

    def test_a_criteria_reply_is_parsed_by_its_own_fields(self):
        names = ("a", "b")
        text = ("READ: x\nPRIOR: nothing\nSCORE: 100\nCRITERION-a: 2\nCRITERION-b: -5\n"
                "STRENGTHS: none\nDOUBTS: none\nUNDERSOLD: none\nOVEREXPLAINED: none\n"
                "OWNED: none\nFLAG-FIXES: none\n")
        reply = panel.parse_reply(text, names)
        self.assertEqual((reply.failure, reply.score), (None, -3))
        self.assertEqual(reply.fields["SCORE"], "100")
        for broken, failure in ((text.replace("CRITERION-b: -5\n", ""), "missing CRITERION-b"),
                                (text + "CRITERION-a: 1\n", "CRITERION-a appears twice"),
                                (text.replace("CRITERION-b: -5", "CRITERION-b: 5.5"),
                                 "CRITERION-b is not an integer"),
                                (text.replace("CRITERION-b: -5", "CRITERION-b: "),
                                 "CRITERION-b is not an integer"),
                                (text.replace("READ: x\n", ""), "missing READ")):
            with self.subTest(failure):
                self.assertEqual(panel.parse_reply(broken, names).failure, failure)
        # Without criteria a CRITERION line is not a field: it runs on from the value before it,
        # as in revision 3, and the reply is read as revision 3 reads it.
        plain = panel.parse_reply(text.replace("SCORE: 100", "SCORE: 4"))
        self.assertEqual((plain.failure, plain.score), ("SCORE is not an integer", None))
        self.assertEqual(plain.fields["SCORE"], "4\nCRITERION-a: 2\nCRITERION-b: -5")

    def test_a_criteria_sum_of_more_than_4300_digits_is_read_and_printed(self):
        before = (sys.get_int_max_str_digits() if hasattr(sys, "get_int_max_str_digits")
                  else None)
        nines, eights = "9" * 4301, "8" * 4301
        fake = ['recruiter | strong | write "%s" in CRITERION-a' % nines,
                'recruiter | version | write "%s" in CRITERION-a' % eights,
                'recruiter | weak | write "0" in CRITERION-a',
                'recruiter | write "1" in CRITERION-b']
        s = Setup(self, lenses=[
            "recruiter | recruiter.lens.txt | author-edited-version no | criteria a,b",
            LENSES[1]], fake_reader=fake, rules=["recruiter | PASS if score at least 7 in 6 of "
                                                 "6; otherwise INCONCLUSIVE"])
        result = s.frozen_run()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        with panel.harness.unlimited_int_digits():
            strong, version = str(int(nines) + 1), str(int(eights) + 1)
        lines = s.result_lines()
        self.assertIn("headroom l1: strong anchor median %s, version median %s"
                      % (strong, version), lines)
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        self.assertEqual((len(strong), len(version)), (4302, 4301))
        if before is not None:
            self.assertEqual(sys.get_int_max_str_digits(), before)

    def test_the_fake_reply_for_a_lens_with_criteria_follows_its_order(self):
        rules = [panel.FakeRule.write("CRITERION-b", "2", lenses=["l1"]),
                 panel.FakeRule.write("CRITERION-a", "1", lenses=["l1"])]
        read = panel.PlannedRead("l1", 9, "r1", "version")
        text = panel.fake_reply(read, rules, "x", criteria=("a", "b", "c"))
        order = [line.split(":")[0] for line in text.splitlines()]
        self.assertEqual(order[:5], ["READ", "PRIOR", "SCORE", "CRITERION-a", "CRITERION-b"])
        self.assertNotIn("CRITERION-c", order)
        with self.assertRaises(ValueError):
            panel.FakeRule.write("CRITERION-", "1")


class UncalibratedCase(Run):
    def test_10_57_without_a_calibration_scores_are_uncalibrated(self):
        rules = ["recruiter | " + SIX_PASS, OVERALL_12]
        _s, _result, lines = self.done(fake_reader=RANK, rules=rules)
        self.assertIn("calibration: none; scores are uncalibrated", lines)
        verdicts = [x for x in lines if " verdict: " in x]
        self.assertEqual(len(verdicts), 2)
        for line in verdicts:
            self.assertTrue(line.endswith(" [not blind: 0 reads left out] [uncalibrated]"), line)
        _s, _result, lines = self.done(readers=["r1 | fake", "r2 | fake | not-blind"],
                                       fake_reader=RANK, rules=rules)
        for line in [x for x in lines if " verdict: " in x]:
            self.assertTrue(line.endswith(" reads left out] [uncalibrated]"), line)

    def test_the_calibration_line_follows_the_prompt_lines(self):
        s, _result, lines = self.done(lenses=[ABC_LENS, LENSES[1]], fake_reader=ABC)
        at = [i for i, x in enumerate(lines) if x.startswith("prompt sha256:")][0]
        self.assertTrue(lines[at + 1].startswith("prompt sha256 (criteria a,b,c): "))
        self.assertEqual(lines[at + 1].split(": ", 1)[1],
                         sha256_text(panel.criteria_prompt(("a", "b", "c"))))
        self.assertEqual(lines[at + 2], "calibration: none; scores are uncalibrated")
        self.assertEqual(lines[at + 3].split(":")[0], "version")


class EarlierAnswersCase(Run):
    def test_10_61_earlier_answers_hold(self):
        rank = ["recruiter | " + SIX_PASS]
        # 10.2: eight anchor reads are named, and the control lens is still counted.
        _s, _r, lines = self.done(fake_reader=RANK[:3] + ["manager | score 5"],
                                  rules=rank + ["manager | " + SIX_PASS])
        failed = [x for x in lines if x.startswith("anchor gate l2: failed (")][0]
        self.assertEqual(failed.count(" read l2/"), 8)
        self.assertIn("lens l1: counted", lines)
        # 10.8: 28 key rows; 10.34: 28 planned reads, none valid.
        s, _r, _lines = self.done(fake_reader=RANK)
        self.assertEqual(len(s.read(panel.KEY_FILE).splitlines()), 28)
        _s, _r, lines = self.done(fake_reader=["omit SCORE"], rules=rank)
        self.assertIn("DEAD: 0 of 28 planned reads are valid", lines)
        # 10.12: a ceiling of 10 cuts after the recruiter's anchors and two version reads.
        _s, result, lines = self.done(fake_reader=RANK, spend_ceiling="10", rules=rank)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("cut: ran 10 of 28 planned reads at spend ceiling 10", lines)
        self.assertIn("rule r1 (l1) count: score at least 7: 2 of 2 valid reads", lines)
        # 10.33: one missing version read.
        _s, result, lines = self.done(fake_reader=RANK + ["recruiter | version | omit SCORE | "
                                                          "read 9"], rules=rank)
        self.assertIn("missing l1 version: 1 of 6 planned reads (failed 1, not run 0)", lines)
        self.assertIn("rule r1 (l1) completions (missing reads: 1): unsettled: PASS, "
                      "INCONCLUSIVE possible", lines)
        # 10.41: the floor lifts a settled completion.
        _s, _r, lines = self.done(
            fake_reader=RANK + ["recruiter | version | omit SCORE | read 9"],
            rules=[FIVE_OF_SIX], min_valid_reads="5")
        self.assertIn("rule r1 (l1) verdict: PASS" + TAG, lines)
        # 10.44: 14 valid reads per reader.
        _s, _r, lines = self.done(
            readers=["reader-1 | fake | reader-group f1", "reader-2 | fake | reader-group f2"],
            fake_reader=RANK, rules=rank)
        self.assertIn("reader-group f1: 14 valid reads", lines)
        self.assertIn("reader-group f2: 14 valid reads", lines)

    def test_one_blind_reader_leaves_headroom_not_assessed_and_no_pass(self):
        # 10.18's plan, and the plans of 10.35 and 10.39 with one blind reader: 2 strong reads.
        plans = {"10.18": dict(readers=["r1 | fake"], reads_per_reader="2", lenses=LENSES[:1],
                               fake_reader=RANK[:3],
                               rules=["recruiter | PASS if score at least 7 in 2 of 2; "
                                      "otherwise INCONCLUSIVE"]),
                 "10.35": dict(readers=["r1 | fake", "r2 | fake | not-blind"],
                               fake_reader=RANK, rules=["recruiter | " + SIX_PASS, OVERALL_12]),
                 "10.39": dict(readers=["r1 | fake", "r2 | fake | not-blind"],
                               fake_reader=RANK, rules=["recruiter | " + SIX_PASS])}
        for name, plan in plans.items():
            with self.subTest(name):
                _s, _r, lines = self.done(**plan)
                self.assertIn("headroom l1: not assessed (2 valid strong-anchor reads, at "
                              "least 3 needed)", lines)
                self.assertEqual([x for x in lines if " verdict: PASS" in x], [])


# Revision 3's verdict for each rule of each plan of the matrix, as the release before
# revision 4 gave it: (readers, anchor reads per reader, strong anchor score, version
# score, missing read, rule).
REV3 = {
    (1, 1, 7, 2, "missing", "r1"): "FAIL",
    (1, 1, 7, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 1, 7, 2, "missing", "r3"): "FAIL",
    (1, 1, 7, 2, "missing", "r4"): "PASS",
    (1, 1, 7, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 2, "none", "r1"): "FAIL",
    (1, 1, 7, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 1, 7, 2, "none", "r3"): "FAIL",
    (1, 1, 7, 2, "none", "r4"): "PASS",
    (1, 1, 7, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 4, "missing", "r1"): "FAIL",
    (1, 1, 7, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 1, 7, 4, "missing", "r3"): "FAIL",
    (1, 1, 7, 4, "missing", "r4"): "PASS",
    (1, 1, 7, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 4, "none", "r1"): "FAIL",
    (1, 1, 7, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 1, 7, 4, "none", "r3"): "FAIL",
    (1, 1, 7, 4, "none", "r4"): "PASS",
    (1, 1, 7, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 6, "missing", "r2"): "PASS",
    (1, 1, 7, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 1, 7, 6, "missing", "r4"): "PASS",
    (1, 1, 7, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 6, "none", "r2"): "PASS",
    (1, 1, 7, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 1, 7, 6, "none", "r4"): "PASS",
    (1, 1, 7, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 7, "missing", "r2"): "PASS",
    (1, 1, 7, 7, "missing", "r3"): "PASS",
    (1, 1, 7, 7, "missing", "r4"): "PASS",
    (1, 1, 7, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 7, "none", "r2"): "PASS",
    (1, 1, 7, 7, "none", "r3"): "PASS",
    (1, 1, 7, 7, "none", "r4"): "PASS",
    (1, 1, 7, 7, "none", "r5"): "PASS",
    (1, 1, 7, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 8, "missing", "r2"): "PASS",
    (1, 1, 7, 8, "missing", "r3"): "PASS",
    (1, 1, 7, 8, "missing", "r4"): "PASS",
    (1, 1, 7, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 8, "none", "r2"): "PASS",
    (1, 1, 7, 8, "none", "r3"): "PASS",
    (1, 1, 7, 8, "none", "r4"): "PASS",
    (1, 1, 7, 8, "none", "r5"): "PASS",
    (1, 1, 7, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 9, "missing", "r2"): "PASS",
    (1, 1, 7, 9, "missing", "r3"): "PASS",
    (1, 1, 7, 9, "missing", "r4"): "PASS",
    (1, 1, 7, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 7, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 7, 9, "none", "r2"): "PASS",
    (1, 1, 7, 9, "none", "r3"): "PASS",
    (1, 1, 7, 9, "none", "r4"): "PASS",
    (1, 1, 7, 9, "none", "r5"): "PASS",
    (1, 1, 8, 2, "missing", "r1"): "FAIL",
    (1, 1, 8, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 1, 8, 2, "missing", "r3"): "FAIL",
    (1, 1, 8, 2, "missing", "r4"): "PASS",
    (1, 1, 8, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 2, "none", "r1"): "FAIL",
    (1, 1, 8, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 1, 8, 2, "none", "r3"): "FAIL",
    (1, 1, 8, 2, "none", "r4"): "PASS",
    (1, 1, 8, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 4, "missing", "r1"): "FAIL",
    (1, 1, 8, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 1, 8, 4, "missing", "r3"): "FAIL",
    (1, 1, 8, 4, "missing", "r4"): "PASS",
    (1, 1, 8, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 4, "none", "r1"): "FAIL",
    (1, 1, 8, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 1, 8, 4, "none", "r3"): "FAIL",
    (1, 1, 8, 4, "none", "r4"): "PASS",
    (1, 1, 8, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 6, "missing", "r2"): "PASS",
    (1, 1, 8, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 1, 8, 6, "missing", "r4"): "PASS",
    (1, 1, 8, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 6, "none", "r2"): "PASS",
    (1, 1, 8, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 1, 8, 6, "none", "r4"): "PASS",
    (1, 1, 8, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 7, "missing", "r2"): "PASS",
    (1, 1, 8, 7, "missing", "r3"): "PASS",
    (1, 1, 8, 7, "missing", "r4"): "PASS",
    (1, 1, 8, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 7, "none", "r2"): "PASS",
    (1, 1, 8, 7, "none", "r3"): "PASS",
    (1, 1, 8, 7, "none", "r4"): "PASS",
    (1, 1, 8, 7, "none", "r5"): "PASS",
    (1, 1, 8, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 8, "missing", "r2"): "PASS",
    (1, 1, 8, 8, "missing", "r3"): "PASS",
    (1, 1, 8, 8, "missing", "r4"): "PASS",
    (1, 1, 8, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 8, "none", "r2"): "PASS",
    (1, 1, 8, 8, "none", "r3"): "PASS",
    (1, 1, 8, 8, "none", "r4"): "PASS",
    (1, 1, 8, 8, "none", "r5"): "PASS",
    (1, 1, 8, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 9, "missing", "r2"): "PASS",
    (1, 1, 8, 9, "missing", "r3"): "PASS",
    (1, 1, 8, 9, "missing", "r4"): "PASS",
    (1, 1, 8, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 8, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 8, 9, "none", "r2"): "PASS",
    (1, 1, 8, 9, "none", "r3"): "PASS",
    (1, 1, 8, 9, "none", "r4"): "PASS",
    (1, 1, 8, 9, "none", "r5"): "PASS",
    (1, 1, 9, 2, "missing", "r1"): "FAIL",
    (1, 1, 9, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 1, 9, 2, "missing", "r3"): "FAIL",
    (1, 1, 9, 2, "missing", "r4"): "PASS",
    (1, 1, 9, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 2, "none", "r1"): "FAIL",
    (1, 1, 9, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 1, 9, 2, "none", "r3"): "FAIL",
    (1, 1, 9, 2, "none", "r4"): "PASS",
    (1, 1, 9, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 4, "missing", "r1"): "FAIL",
    (1, 1, 9, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 1, 9, 4, "missing", "r3"): "FAIL",
    (1, 1, 9, 4, "missing", "r4"): "PASS",
    (1, 1, 9, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 4, "none", "r1"): "FAIL",
    (1, 1, 9, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 1, 9, 4, "none", "r3"): "FAIL",
    (1, 1, 9, 4, "none", "r4"): "PASS",
    (1, 1, 9, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 6, "missing", "r2"): "PASS",
    (1, 1, 9, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 1, 9, 6, "missing", "r4"): "PASS",
    (1, 1, 9, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 6, "none", "r2"): "PASS",
    (1, 1, 9, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 1, 9, 6, "none", "r4"): "PASS",
    (1, 1, 9, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 7, "missing", "r2"): "PASS",
    (1, 1, 9, 7, "missing", "r3"): "PASS",
    (1, 1, 9, 7, "missing", "r4"): "PASS",
    (1, 1, 9, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 7, "none", "r2"): "PASS",
    (1, 1, 9, 7, "none", "r3"): "PASS",
    (1, 1, 9, 7, "none", "r4"): "PASS",
    (1, 1, 9, 7, "none", "r5"): "PASS",
    (1, 1, 9, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 8, "missing", "r2"): "PASS",
    (1, 1, 9, 8, "missing", "r3"): "PASS",
    (1, 1, 9, 8, "missing", "r4"): "PASS",
    (1, 1, 9, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 8, "none", "r2"): "PASS",
    (1, 1, 9, 8, "none", "r3"): "PASS",
    (1, 1, 9, 8, "none", "r4"): "PASS",
    (1, 1, 9, 8, "none", "r5"): "PASS",
    (1, 1, 9, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 9, "missing", "r2"): "PASS",
    (1, 1, 9, 9, "missing", "r3"): "PASS",
    (1, 1, 9, 9, "missing", "r4"): "PASS",
    (1, 1, 9, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 1, 9, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 1, 9, 9, "none", "r2"): "PASS",
    (1, 1, 9, 9, "none", "r3"): "PASS",
    (1, 1, 9, 9, "none", "r4"): "PASS",
    (1, 1, 9, 9, "none", "r5"): "PASS",
    (1, 2, 7, 2, "missing", "r1"): "FAIL",
    (1, 2, 7, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 2, 7, 2, "missing", "r3"): "FAIL",
    (1, 2, 7, 2, "missing", "r4"): "PASS",
    (1, 2, 7, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 2, "none", "r1"): "FAIL",
    (1, 2, 7, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 2, 7, 2, "none", "r3"): "FAIL",
    (1, 2, 7, 2, "none", "r4"): "PASS",
    (1, 2, 7, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 4, "missing", "r1"): "FAIL",
    (1, 2, 7, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 2, 7, 4, "missing", "r3"): "FAIL",
    (1, 2, 7, 4, "missing", "r4"): "PASS",
    (1, 2, 7, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 4, "none", "r1"): "FAIL",
    (1, 2, 7, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 2, 7, 4, "none", "r3"): "FAIL",
    (1, 2, 7, 4, "none", "r4"): "PASS",
    (1, 2, 7, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 6, "missing", "r2"): "PASS",
    (1, 2, 7, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 2, 7, 6, "missing", "r4"): "PASS",
    (1, 2, 7, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 6, "none", "r2"): "PASS",
    (1, 2, 7, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 2, 7, 6, "none", "r4"): "PASS",
    (1, 2, 7, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 7, "missing", "r2"): "PASS",
    (1, 2, 7, 7, "missing", "r3"): "PASS",
    (1, 2, 7, 7, "missing", "r4"): "PASS",
    (1, 2, 7, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 7, "none", "r2"): "PASS",
    (1, 2, 7, 7, "none", "r3"): "PASS",
    (1, 2, 7, 7, "none", "r4"): "PASS",
    (1, 2, 7, 7, "none", "r5"): "PASS",
    (1, 2, 7, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 8, "missing", "r2"): "PASS",
    (1, 2, 7, 8, "missing", "r3"): "PASS",
    (1, 2, 7, 8, "missing", "r4"): "PASS",
    (1, 2, 7, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 8, "none", "r2"): "PASS",
    (1, 2, 7, 8, "none", "r3"): "PASS",
    (1, 2, 7, 8, "none", "r4"): "PASS",
    (1, 2, 7, 8, "none", "r5"): "PASS",
    (1, 2, 7, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 9, "missing", "r2"): "PASS",
    (1, 2, 7, 9, "missing", "r3"): "PASS",
    (1, 2, 7, 9, "missing", "r4"): "PASS",
    (1, 2, 7, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 7, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 7, 9, "none", "r2"): "PASS",
    (1, 2, 7, 9, "none", "r3"): "PASS",
    (1, 2, 7, 9, "none", "r4"): "PASS",
    (1, 2, 7, 9, "none", "r5"): "PASS",
    (1, 2, 8, 2, "missing", "r1"): "FAIL",
    (1, 2, 8, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 2, 8, 2, "missing", "r3"): "FAIL",
    (1, 2, 8, 2, "missing", "r4"): "PASS",
    (1, 2, 8, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 2, "none", "r1"): "FAIL",
    (1, 2, 8, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 2, 8, 2, "none", "r3"): "FAIL",
    (1, 2, 8, 2, "none", "r4"): "PASS",
    (1, 2, 8, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 4, "missing", "r1"): "FAIL",
    (1, 2, 8, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 2, 8, 4, "missing", "r3"): "FAIL",
    (1, 2, 8, 4, "missing", "r4"): "PASS",
    (1, 2, 8, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 4, "none", "r1"): "FAIL",
    (1, 2, 8, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 2, 8, 4, "none", "r3"): "FAIL",
    (1, 2, 8, 4, "none", "r4"): "PASS",
    (1, 2, 8, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 6, "missing", "r2"): "PASS",
    (1, 2, 8, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 2, 8, 6, "missing", "r4"): "PASS",
    (1, 2, 8, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 6, "none", "r2"): "PASS",
    (1, 2, 8, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 2, 8, 6, "none", "r4"): "PASS",
    (1, 2, 8, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 7, "missing", "r2"): "PASS",
    (1, 2, 8, 7, "missing", "r3"): "PASS",
    (1, 2, 8, 7, "missing", "r4"): "PASS",
    (1, 2, 8, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 7, "none", "r2"): "PASS",
    (1, 2, 8, 7, "none", "r3"): "PASS",
    (1, 2, 8, 7, "none", "r4"): "PASS",
    (1, 2, 8, 7, "none", "r5"): "PASS",
    (1, 2, 8, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 8, "missing", "r2"): "PASS",
    (1, 2, 8, 8, "missing", "r3"): "PASS",
    (1, 2, 8, 8, "missing", "r4"): "PASS",
    (1, 2, 8, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 8, "none", "r2"): "PASS",
    (1, 2, 8, 8, "none", "r3"): "PASS",
    (1, 2, 8, 8, "none", "r4"): "PASS",
    (1, 2, 8, 8, "none", "r5"): "PASS",
    (1, 2, 8, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 9, "missing", "r2"): "PASS",
    (1, 2, 8, 9, "missing", "r3"): "PASS",
    (1, 2, 8, 9, "missing", "r4"): "PASS",
    (1, 2, 8, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 8, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 8, 9, "none", "r2"): "PASS",
    (1, 2, 8, 9, "none", "r3"): "PASS",
    (1, 2, 8, 9, "none", "r4"): "PASS",
    (1, 2, 8, 9, "none", "r5"): "PASS",
    (1, 2, 9, 2, "missing", "r1"): "FAIL",
    (1, 2, 9, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 2, 9, 2, "missing", "r3"): "FAIL",
    (1, 2, 9, 2, "missing", "r4"): "PASS",
    (1, 2, 9, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 2, "none", "r1"): "FAIL",
    (1, 2, 9, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 2, 9, 2, "none", "r3"): "FAIL",
    (1, 2, 9, 2, "none", "r4"): "PASS",
    (1, 2, 9, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 4, "missing", "r1"): "FAIL",
    (1, 2, 9, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 2, 9, 4, "missing", "r3"): "FAIL",
    (1, 2, 9, 4, "missing", "r4"): "PASS",
    (1, 2, 9, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 4, "none", "r1"): "FAIL",
    (1, 2, 9, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 2, 9, 4, "none", "r3"): "FAIL",
    (1, 2, 9, 4, "none", "r4"): "PASS",
    (1, 2, 9, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 6, "missing", "r2"): "PASS",
    (1, 2, 9, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 2, 9, 6, "missing", "r4"): "PASS",
    (1, 2, 9, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 6, "none", "r2"): "PASS",
    (1, 2, 9, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 2, 9, 6, "none", "r4"): "PASS",
    (1, 2, 9, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 7, "missing", "r2"): "PASS",
    (1, 2, 9, 7, "missing", "r3"): "PASS",
    (1, 2, 9, 7, "missing", "r4"): "PASS",
    (1, 2, 9, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 7, "none", "r2"): "PASS",
    (1, 2, 9, 7, "none", "r3"): "PASS",
    (1, 2, 9, 7, "none", "r4"): "PASS",
    (1, 2, 9, 7, "none", "r5"): "PASS",
    (1, 2, 9, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 8, "missing", "r2"): "PASS",
    (1, 2, 9, 8, "missing", "r3"): "PASS",
    (1, 2, 9, 8, "missing", "r4"): "PASS",
    (1, 2, 9, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 8, "none", "r2"): "PASS",
    (1, 2, 9, 8, "none", "r3"): "PASS",
    (1, 2, 9, 8, "none", "r4"): "PASS",
    (1, 2, 9, 8, "none", "r5"): "PASS",
    (1, 2, 9, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 9, "missing", "r2"): "PASS",
    (1, 2, 9, 9, "missing", "r3"): "PASS",
    (1, 2, 9, 9, "missing", "r4"): "PASS",
    (1, 2, 9, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 2, 9, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 2, 9, 9, "none", "r2"): "PASS",
    (1, 2, 9, 9, "none", "r3"): "PASS",
    (1, 2, 9, 9, "none", "r4"): "PASS",
    (1, 2, 9, 9, "none", "r5"): "PASS",
    (1, 3, 7, 2, "missing", "r1"): "FAIL",
    (1, 3, 7, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 3, 7, 2, "missing", "r3"): "FAIL",
    (1, 3, 7, 2, "missing", "r4"): "PASS",
    (1, 3, 7, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 2, "none", "r1"): "FAIL",
    (1, 3, 7, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 3, 7, 2, "none", "r3"): "FAIL",
    (1, 3, 7, 2, "none", "r4"): "PASS",
    (1, 3, 7, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 4, "missing", "r1"): "FAIL",
    (1, 3, 7, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 3, 7, 4, "missing", "r3"): "FAIL",
    (1, 3, 7, 4, "missing", "r4"): "PASS",
    (1, 3, 7, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 4, "none", "r1"): "FAIL",
    (1, 3, 7, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 3, 7, 4, "none", "r3"): "FAIL",
    (1, 3, 7, 4, "none", "r4"): "PASS",
    (1, 3, 7, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 6, "missing", "r2"): "PASS",
    (1, 3, 7, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 3, 7, 6, "missing", "r4"): "PASS",
    (1, 3, 7, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 6, "none", "r2"): "PASS",
    (1, 3, 7, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 3, 7, 6, "none", "r4"): "PASS",
    (1, 3, 7, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 7, "missing", "r2"): "PASS",
    (1, 3, 7, 7, "missing", "r3"): "PASS",
    (1, 3, 7, 7, "missing", "r4"): "PASS",
    (1, 3, 7, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 7, "none", "r2"): "PASS",
    (1, 3, 7, 7, "none", "r3"): "PASS",
    (1, 3, 7, 7, "none", "r4"): "PASS",
    (1, 3, 7, 7, "none", "r5"): "PASS",
    (1, 3, 7, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 8, "missing", "r2"): "PASS",
    (1, 3, 7, 8, "missing", "r3"): "PASS",
    (1, 3, 7, 8, "missing", "r4"): "PASS",
    (1, 3, 7, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 8, "none", "r2"): "PASS",
    (1, 3, 7, 8, "none", "r3"): "PASS",
    (1, 3, 7, 8, "none", "r4"): "PASS",
    (1, 3, 7, 8, "none", "r5"): "PASS",
    (1, 3, 7, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 9, "missing", "r2"): "PASS",
    (1, 3, 7, 9, "missing", "r3"): "PASS",
    (1, 3, 7, 9, "missing", "r4"): "PASS",
    (1, 3, 7, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 7, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 7, 9, "none", "r2"): "PASS",
    (1, 3, 7, 9, "none", "r3"): "PASS",
    (1, 3, 7, 9, "none", "r4"): "PASS",
    (1, 3, 7, 9, "none", "r5"): "PASS",
    (1, 3, 8, 2, "missing", "r1"): "FAIL",
    (1, 3, 8, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 3, 8, 2, "missing", "r3"): "FAIL",
    (1, 3, 8, 2, "missing", "r4"): "PASS",
    (1, 3, 8, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 2, "none", "r1"): "FAIL",
    (1, 3, 8, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 3, 8, 2, "none", "r3"): "FAIL",
    (1, 3, 8, 2, "none", "r4"): "PASS",
    (1, 3, 8, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 4, "missing", "r1"): "FAIL",
    (1, 3, 8, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 3, 8, 4, "missing", "r3"): "FAIL",
    (1, 3, 8, 4, "missing", "r4"): "PASS",
    (1, 3, 8, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 4, "none", "r1"): "FAIL",
    (1, 3, 8, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 3, 8, 4, "none", "r3"): "FAIL",
    (1, 3, 8, 4, "none", "r4"): "PASS",
    (1, 3, 8, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 6, "missing", "r2"): "PASS",
    (1, 3, 8, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 3, 8, 6, "missing", "r4"): "PASS",
    (1, 3, 8, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 6, "none", "r2"): "PASS",
    (1, 3, 8, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 3, 8, 6, "none", "r4"): "PASS",
    (1, 3, 8, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 7, "missing", "r2"): "PASS",
    (1, 3, 8, 7, "missing", "r3"): "PASS",
    (1, 3, 8, 7, "missing", "r4"): "PASS",
    (1, 3, 8, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 7, "none", "r2"): "PASS",
    (1, 3, 8, 7, "none", "r3"): "PASS",
    (1, 3, 8, 7, "none", "r4"): "PASS",
    (1, 3, 8, 7, "none", "r5"): "PASS",
    (1, 3, 8, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 8, "missing", "r2"): "PASS",
    (1, 3, 8, 8, "missing", "r3"): "PASS",
    (1, 3, 8, 8, "missing", "r4"): "PASS",
    (1, 3, 8, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 8, "none", "r2"): "PASS",
    (1, 3, 8, 8, "none", "r3"): "PASS",
    (1, 3, 8, 8, "none", "r4"): "PASS",
    (1, 3, 8, 8, "none", "r5"): "PASS",
    (1, 3, 8, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 9, "missing", "r2"): "PASS",
    (1, 3, 8, 9, "missing", "r3"): "PASS",
    (1, 3, 8, 9, "missing", "r4"): "PASS",
    (1, 3, 8, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 8, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 8, 9, "none", "r2"): "PASS",
    (1, 3, 8, 9, "none", "r3"): "PASS",
    (1, 3, 8, 9, "none", "r4"): "PASS",
    (1, 3, 8, 9, "none", "r5"): "PASS",
    (1, 3, 9, 2, "missing", "r1"): "FAIL",
    (1, 3, 9, 2, "missing", "r2"): "INCONCLUSIVE",
    (1, 3, 9, 2, "missing", "r3"): "FAIL",
    (1, 3, 9, 2, "missing", "r4"): "PASS",
    (1, 3, 9, 2, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 2, "none", "r1"): "FAIL",
    (1, 3, 9, 2, "none", "r2"): "INCONCLUSIVE",
    (1, 3, 9, 2, "none", "r3"): "FAIL",
    (1, 3, 9, 2, "none", "r4"): "PASS",
    (1, 3, 9, 2, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 4, "missing", "r1"): "FAIL",
    (1, 3, 9, 4, "missing", "r2"): "INCONCLUSIVE",
    (1, 3, 9, 4, "missing", "r3"): "FAIL",
    (1, 3, 9, 4, "missing", "r4"): "PASS",
    (1, 3, 9, 4, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 4, "none", "r1"): "FAIL",
    (1, 3, 9, 4, "none", "r2"): "INCONCLUSIVE",
    (1, 3, 9, 4, "none", "r3"): "FAIL",
    (1, 3, 9, 4, "none", "r4"): "PASS",
    (1, 3, 9, 4, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 6, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 6, "missing", "r2"): "PASS",
    (1, 3, 9, 6, "missing", "r3"): "INCONCLUSIVE",
    (1, 3, 9, 6, "missing", "r4"): "PASS",
    (1, 3, 9, 6, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 6, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 6, "none", "r2"): "PASS",
    (1, 3, 9, 6, "none", "r3"): "INCONCLUSIVE",
    (1, 3, 9, 6, "none", "r4"): "PASS",
    (1, 3, 9, 6, "none", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 7, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 7, "missing", "r2"): "PASS",
    (1, 3, 9, 7, "missing", "r3"): "PASS",
    (1, 3, 9, 7, "missing", "r4"): "PASS",
    (1, 3, 9, 7, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 7, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 7, "none", "r2"): "PASS",
    (1, 3, 9, 7, "none", "r3"): "PASS",
    (1, 3, 9, 7, "none", "r4"): "PASS",
    (1, 3, 9, 7, "none", "r5"): "PASS",
    (1, 3, 9, 8, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 8, "missing", "r2"): "PASS",
    (1, 3, 9, 8, "missing", "r3"): "PASS",
    (1, 3, 9, 8, "missing", "r4"): "PASS",
    (1, 3, 9, 8, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 8, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 8, "none", "r2"): "PASS",
    (1, 3, 9, 8, "none", "r3"): "PASS",
    (1, 3, 9, 8, "none", "r4"): "PASS",
    (1, 3, 9, 8, "none", "r5"): "PASS",
    (1, 3, 9, 9, "missing", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 9, "missing", "r2"): "PASS",
    (1, 3, 9, 9, "missing", "r3"): "PASS",
    (1, 3, 9, 9, "missing", "r4"): "PASS",
    (1, 3, 9, 9, "missing", "r5"): "INCONCLUSIVE",
    (1, 3, 9, 9, "none", "r1"): "INCONCLUSIVE",
    (1, 3, 9, 9, "none", "r2"): "PASS",
    (1, 3, 9, 9, "none", "r3"): "PASS",
    (1, 3, 9, 9, "none", "r4"): "PASS",
    (1, 3, 9, 9, "none", "r5"): "PASS",
    (2, 1, 7, 2, "missing", "r1"): "FAIL",
    (2, 1, 7, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 1, 7, 2, "missing", "r3"): "FAIL",
    (2, 1, 7, 2, "missing", "r4"): "PASS",
    (2, 1, 7, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 7, 2, "none", "r1"): "FAIL",
    (2, 1, 7, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 1, 7, 2, "none", "r3"): "FAIL",
    (2, 1, 7, 2, "none", "r4"): "PASS",
    (2, 1, 7, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 7, 4, "missing", "r1"): "FAIL",
    (2, 1, 7, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 1, 7, 4, "missing", "r3"): "FAIL",
    (2, 1, 7, 4, "missing", "r4"): "PASS",
    (2, 1, 7, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 7, 4, "none", "r1"): "FAIL",
    (2, 1, 7, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 1, 7, 4, "none", "r3"): "FAIL",
    (2, 1, 7, 4, "none", "r4"): "PASS",
    (2, 1, 7, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 7, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 7, 6, "missing", "r2"): "PASS",
    (2, 1, 7, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 1, 7, 6, "missing", "r4"): "PASS",
    (2, 1, 7, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 7, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 1, 7, 6, "none", "r2"): "PASS",
    (2, 1, 7, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 1, 7, 6, "none", "r4"): "PASS",
    (2, 1, 7, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 7, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 7, 7, "missing", "r2"): "PASS",
    (2, 1, 7, 7, "missing", "r3"): "PASS",
    (2, 1, 7, 7, "missing", "r4"): "PASS",
    (2, 1, 7, 7, "missing", "r5"): "PASS",
    (2, 1, 7, 7, "none", "r1"): "PASS",
    (2, 1, 7, 7, "none", "r2"): "PASS",
    (2, 1, 7, 7, "none", "r3"): "PASS",
    (2, 1, 7, 7, "none", "r4"): "PASS",
    (2, 1, 7, 7, "none", "r5"): "PASS",
    (2, 1, 7, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 7, 8, "missing", "r2"): "PASS",
    (2, 1, 7, 8, "missing", "r3"): "PASS",
    (2, 1, 7, 8, "missing", "r4"): "PASS",
    (2, 1, 7, 8, "missing", "r5"): "PASS",
    (2, 1, 7, 8, "none", "r1"): "PASS",
    (2, 1, 7, 8, "none", "r2"): "PASS",
    (2, 1, 7, 8, "none", "r3"): "PASS",
    (2, 1, 7, 8, "none", "r4"): "PASS",
    (2, 1, 7, 8, "none", "r5"): "PASS",
    (2, 1, 7, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 7, 9, "missing", "r2"): "PASS",
    (2, 1, 7, 9, "missing", "r3"): "PASS",
    (2, 1, 7, 9, "missing", "r4"): "PASS",
    (2, 1, 7, 9, "missing", "r5"): "PASS",
    (2, 1, 7, 9, "none", "r1"): "PASS",
    (2, 1, 7, 9, "none", "r2"): "PASS",
    (2, 1, 7, 9, "none", "r3"): "PASS",
    (2, 1, 7, 9, "none", "r4"): "PASS",
    (2, 1, 7, 9, "none", "r5"): "PASS",
    (2, 1, 8, 2, "missing", "r1"): "FAIL",
    (2, 1, 8, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 1, 8, 2, "missing", "r3"): "FAIL",
    (2, 1, 8, 2, "missing", "r4"): "PASS",
    (2, 1, 8, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 8, 2, "none", "r1"): "FAIL",
    (2, 1, 8, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 1, 8, 2, "none", "r3"): "FAIL",
    (2, 1, 8, 2, "none", "r4"): "PASS",
    (2, 1, 8, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 8, 4, "missing", "r1"): "FAIL",
    (2, 1, 8, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 1, 8, 4, "missing", "r3"): "FAIL",
    (2, 1, 8, 4, "missing", "r4"): "PASS",
    (2, 1, 8, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 8, 4, "none", "r1"): "FAIL",
    (2, 1, 8, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 1, 8, 4, "none", "r3"): "FAIL",
    (2, 1, 8, 4, "none", "r4"): "PASS",
    (2, 1, 8, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 8, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 8, 6, "missing", "r2"): "PASS",
    (2, 1, 8, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 1, 8, 6, "missing", "r4"): "PASS",
    (2, 1, 8, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 8, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 1, 8, 6, "none", "r2"): "PASS",
    (2, 1, 8, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 1, 8, 6, "none", "r4"): "PASS",
    (2, 1, 8, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 8, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 8, 7, "missing", "r2"): "PASS",
    (2, 1, 8, 7, "missing", "r3"): "PASS",
    (2, 1, 8, 7, "missing", "r4"): "PASS",
    (2, 1, 8, 7, "missing", "r5"): "PASS",
    (2, 1, 8, 7, "none", "r1"): "PASS",
    (2, 1, 8, 7, "none", "r2"): "PASS",
    (2, 1, 8, 7, "none", "r3"): "PASS",
    (2, 1, 8, 7, "none", "r4"): "PASS",
    (2, 1, 8, 7, "none", "r5"): "PASS",
    (2, 1, 8, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 8, 8, "missing", "r2"): "PASS",
    (2, 1, 8, 8, "missing", "r3"): "PASS",
    (2, 1, 8, 8, "missing", "r4"): "PASS",
    (2, 1, 8, 8, "missing", "r5"): "PASS",
    (2, 1, 8, 8, "none", "r1"): "PASS",
    (2, 1, 8, 8, "none", "r2"): "PASS",
    (2, 1, 8, 8, "none", "r3"): "PASS",
    (2, 1, 8, 8, "none", "r4"): "PASS",
    (2, 1, 8, 8, "none", "r5"): "PASS",
    (2, 1, 8, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 8, 9, "missing", "r2"): "PASS",
    (2, 1, 8, 9, "missing", "r3"): "PASS",
    (2, 1, 8, 9, "missing", "r4"): "PASS",
    (2, 1, 8, 9, "missing", "r5"): "PASS",
    (2, 1, 8, 9, "none", "r1"): "PASS",
    (2, 1, 8, 9, "none", "r2"): "PASS",
    (2, 1, 8, 9, "none", "r3"): "PASS",
    (2, 1, 8, 9, "none", "r4"): "PASS",
    (2, 1, 8, 9, "none", "r5"): "PASS",
    (2, 1, 9, 2, "missing", "r1"): "FAIL",
    (2, 1, 9, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 1, 9, 2, "missing", "r3"): "FAIL",
    (2, 1, 9, 2, "missing", "r4"): "PASS",
    (2, 1, 9, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 9, 2, "none", "r1"): "FAIL",
    (2, 1, 9, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 1, 9, 2, "none", "r3"): "FAIL",
    (2, 1, 9, 2, "none", "r4"): "PASS",
    (2, 1, 9, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 9, 4, "missing", "r1"): "FAIL",
    (2, 1, 9, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 1, 9, 4, "missing", "r3"): "FAIL",
    (2, 1, 9, 4, "missing", "r4"): "PASS",
    (2, 1, 9, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 9, 4, "none", "r1"): "FAIL",
    (2, 1, 9, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 1, 9, 4, "none", "r3"): "FAIL",
    (2, 1, 9, 4, "none", "r4"): "PASS",
    (2, 1, 9, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 9, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 9, 6, "missing", "r2"): "PASS",
    (2, 1, 9, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 1, 9, 6, "missing", "r4"): "PASS",
    (2, 1, 9, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 1, 9, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 1, 9, 6, "none", "r2"): "PASS",
    (2, 1, 9, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 1, 9, 6, "none", "r4"): "PASS",
    (2, 1, 9, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 1, 9, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 9, 7, "missing", "r2"): "PASS",
    (2, 1, 9, 7, "missing", "r3"): "PASS",
    (2, 1, 9, 7, "missing", "r4"): "PASS",
    (2, 1, 9, 7, "missing", "r5"): "PASS",
    (2, 1, 9, 7, "none", "r1"): "PASS",
    (2, 1, 9, 7, "none", "r2"): "PASS",
    (2, 1, 9, 7, "none", "r3"): "PASS",
    (2, 1, 9, 7, "none", "r4"): "PASS",
    (2, 1, 9, 7, "none", "r5"): "PASS",
    (2, 1, 9, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 9, 8, "missing", "r2"): "PASS",
    (2, 1, 9, 8, "missing", "r3"): "PASS",
    (2, 1, 9, 8, "missing", "r4"): "PASS",
    (2, 1, 9, 8, "missing", "r5"): "PASS",
    (2, 1, 9, 8, "none", "r1"): "PASS",
    (2, 1, 9, 8, "none", "r2"): "PASS",
    (2, 1, 9, 8, "none", "r3"): "PASS",
    (2, 1, 9, 8, "none", "r4"): "PASS",
    (2, 1, 9, 8, "none", "r5"): "PASS",
    (2, 1, 9, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 1, 9, 9, "missing", "r2"): "PASS",
    (2, 1, 9, 9, "missing", "r3"): "PASS",
    (2, 1, 9, 9, "missing", "r4"): "PASS",
    (2, 1, 9, 9, "missing", "r5"): "PASS",
    (2, 1, 9, 9, "none", "r1"): "PASS",
    (2, 1, 9, 9, "none", "r2"): "PASS",
    (2, 1, 9, 9, "none", "r3"): "PASS",
    (2, 1, 9, 9, "none", "r4"): "PASS",
    (2, 1, 9, 9, "none", "r5"): "PASS",
    (2, 2, 7, 2, "missing", "r1"): "FAIL",
    (2, 2, 7, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 2, 7, 2, "missing", "r3"): "FAIL",
    (2, 2, 7, 2, "missing", "r4"): "PASS",
    (2, 2, 7, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 7, 2, "none", "r1"): "FAIL",
    (2, 2, 7, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 2, 7, 2, "none", "r3"): "FAIL",
    (2, 2, 7, 2, "none", "r4"): "PASS",
    (2, 2, 7, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 7, 4, "missing", "r1"): "FAIL",
    (2, 2, 7, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 2, 7, 4, "missing", "r3"): "FAIL",
    (2, 2, 7, 4, "missing", "r4"): "PASS",
    (2, 2, 7, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 7, 4, "none", "r1"): "FAIL",
    (2, 2, 7, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 2, 7, 4, "none", "r3"): "FAIL",
    (2, 2, 7, 4, "none", "r4"): "PASS",
    (2, 2, 7, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 7, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 7, 6, "missing", "r2"): "PASS",
    (2, 2, 7, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 2, 7, 6, "missing", "r4"): "PASS",
    (2, 2, 7, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 7, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 2, 7, 6, "none", "r2"): "PASS",
    (2, 2, 7, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 2, 7, 6, "none", "r4"): "PASS",
    (2, 2, 7, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 7, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 7, 7, "missing", "r2"): "PASS",
    (2, 2, 7, 7, "missing", "r3"): "PASS",
    (2, 2, 7, 7, "missing", "r4"): "PASS",
    (2, 2, 7, 7, "missing", "r5"): "PASS",
    (2, 2, 7, 7, "none", "r1"): "PASS",
    (2, 2, 7, 7, "none", "r2"): "PASS",
    (2, 2, 7, 7, "none", "r3"): "PASS",
    (2, 2, 7, 7, "none", "r4"): "PASS",
    (2, 2, 7, 7, "none", "r5"): "PASS",
    (2, 2, 7, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 7, 8, "missing", "r2"): "PASS",
    (2, 2, 7, 8, "missing", "r3"): "PASS",
    (2, 2, 7, 8, "missing", "r4"): "PASS",
    (2, 2, 7, 8, "missing", "r5"): "PASS",
    (2, 2, 7, 8, "none", "r1"): "PASS",
    (2, 2, 7, 8, "none", "r2"): "PASS",
    (2, 2, 7, 8, "none", "r3"): "PASS",
    (2, 2, 7, 8, "none", "r4"): "PASS",
    (2, 2, 7, 8, "none", "r5"): "PASS",
    (2, 2, 7, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 7, 9, "missing", "r2"): "PASS",
    (2, 2, 7, 9, "missing", "r3"): "PASS",
    (2, 2, 7, 9, "missing", "r4"): "PASS",
    (2, 2, 7, 9, "missing", "r5"): "PASS",
    (2, 2, 7, 9, "none", "r1"): "PASS",
    (2, 2, 7, 9, "none", "r2"): "PASS",
    (2, 2, 7, 9, "none", "r3"): "PASS",
    (2, 2, 7, 9, "none", "r4"): "PASS",
    (2, 2, 7, 9, "none", "r5"): "PASS",
    (2, 2, 8, 2, "missing", "r1"): "FAIL",
    (2, 2, 8, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 2, 8, 2, "missing", "r3"): "FAIL",
    (2, 2, 8, 2, "missing", "r4"): "PASS",
    (2, 2, 8, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 8, 2, "none", "r1"): "FAIL",
    (2, 2, 8, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 2, 8, 2, "none", "r3"): "FAIL",
    (2, 2, 8, 2, "none", "r4"): "PASS",
    (2, 2, 8, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 8, 4, "missing", "r1"): "FAIL",
    (2, 2, 8, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 2, 8, 4, "missing", "r3"): "FAIL",
    (2, 2, 8, 4, "missing", "r4"): "PASS",
    (2, 2, 8, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 8, 4, "none", "r1"): "FAIL",
    (2, 2, 8, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 2, 8, 4, "none", "r3"): "FAIL",
    (2, 2, 8, 4, "none", "r4"): "PASS",
    (2, 2, 8, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 8, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 8, 6, "missing", "r2"): "PASS",
    (2, 2, 8, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 2, 8, 6, "missing", "r4"): "PASS",
    (2, 2, 8, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 8, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 2, 8, 6, "none", "r2"): "PASS",
    (2, 2, 8, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 2, 8, 6, "none", "r4"): "PASS",
    (2, 2, 8, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 8, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 8, 7, "missing", "r2"): "PASS",
    (2, 2, 8, 7, "missing", "r3"): "PASS",
    (2, 2, 8, 7, "missing", "r4"): "PASS",
    (2, 2, 8, 7, "missing", "r5"): "PASS",
    (2, 2, 8, 7, "none", "r1"): "PASS",
    (2, 2, 8, 7, "none", "r2"): "PASS",
    (2, 2, 8, 7, "none", "r3"): "PASS",
    (2, 2, 8, 7, "none", "r4"): "PASS",
    (2, 2, 8, 7, "none", "r5"): "PASS",
    (2, 2, 8, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 8, 8, "missing", "r2"): "PASS",
    (2, 2, 8, 8, "missing", "r3"): "PASS",
    (2, 2, 8, 8, "missing", "r4"): "PASS",
    (2, 2, 8, 8, "missing", "r5"): "PASS",
    (2, 2, 8, 8, "none", "r1"): "PASS",
    (2, 2, 8, 8, "none", "r2"): "PASS",
    (2, 2, 8, 8, "none", "r3"): "PASS",
    (2, 2, 8, 8, "none", "r4"): "PASS",
    (2, 2, 8, 8, "none", "r5"): "PASS",
    (2, 2, 8, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 8, 9, "missing", "r2"): "PASS",
    (2, 2, 8, 9, "missing", "r3"): "PASS",
    (2, 2, 8, 9, "missing", "r4"): "PASS",
    (2, 2, 8, 9, "missing", "r5"): "PASS",
    (2, 2, 8, 9, "none", "r1"): "PASS",
    (2, 2, 8, 9, "none", "r2"): "PASS",
    (2, 2, 8, 9, "none", "r3"): "PASS",
    (2, 2, 8, 9, "none", "r4"): "PASS",
    (2, 2, 8, 9, "none", "r5"): "PASS",
    (2, 2, 9, 2, "missing", "r1"): "FAIL",
    (2, 2, 9, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 2, 9, 2, "missing", "r3"): "FAIL",
    (2, 2, 9, 2, "missing", "r4"): "PASS",
    (2, 2, 9, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 9, 2, "none", "r1"): "FAIL",
    (2, 2, 9, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 2, 9, 2, "none", "r3"): "FAIL",
    (2, 2, 9, 2, "none", "r4"): "PASS",
    (2, 2, 9, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 9, 4, "missing", "r1"): "FAIL",
    (2, 2, 9, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 2, 9, 4, "missing", "r3"): "FAIL",
    (2, 2, 9, 4, "missing", "r4"): "PASS",
    (2, 2, 9, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 9, 4, "none", "r1"): "FAIL",
    (2, 2, 9, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 2, 9, 4, "none", "r3"): "FAIL",
    (2, 2, 9, 4, "none", "r4"): "PASS",
    (2, 2, 9, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 9, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 9, 6, "missing", "r2"): "PASS",
    (2, 2, 9, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 2, 9, 6, "missing", "r4"): "PASS",
    (2, 2, 9, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 2, 9, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 2, 9, 6, "none", "r2"): "PASS",
    (2, 2, 9, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 2, 9, 6, "none", "r4"): "PASS",
    (2, 2, 9, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 2, 9, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 9, 7, "missing", "r2"): "PASS",
    (2, 2, 9, 7, "missing", "r3"): "PASS",
    (2, 2, 9, 7, "missing", "r4"): "PASS",
    (2, 2, 9, 7, "missing", "r5"): "PASS",
    (2, 2, 9, 7, "none", "r1"): "PASS",
    (2, 2, 9, 7, "none", "r2"): "PASS",
    (2, 2, 9, 7, "none", "r3"): "PASS",
    (2, 2, 9, 7, "none", "r4"): "PASS",
    (2, 2, 9, 7, "none", "r5"): "PASS",
    (2, 2, 9, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 9, 8, "missing", "r2"): "PASS",
    (2, 2, 9, 8, "missing", "r3"): "PASS",
    (2, 2, 9, 8, "missing", "r4"): "PASS",
    (2, 2, 9, 8, "missing", "r5"): "PASS",
    (2, 2, 9, 8, "none", "r1"): "PASS",
    (2, 2, 9, 8, "none", "r2"): "PASS",
    (2, 2, 9, 8, "none", "r3"): "PASS",
    (2, 2, 9, 8, "none", "r4"): "PASS",
    (2, 2, 9, 8, "none", "r5"): "PASS",
    (2, 2, 9, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 2, 9, 9, "missing", "r2"): "PASS",
    (2, 2, 9, 9, "missing", "r3"): "PASS",
    (2, 2, 9, 9, "missing", "r4"): "PASS",
    (2, 2, 9, 9, "missing", "r5"): "PASS",
    (2, 2, 9, 9, "none", "r1"): "PASS",
    (2, 2, 9, 9, "none", "r2"): "PASS",
    (2, 2, 9, 9, "none", "r3"): "PASS",
    (2, 2, 9, 9, "none", "r4"): "PASS",
    (2, 2, 9, 9, "none", "r5"): "PASS",
    (2, 3, 7, 2, "missing", "r1"): "FAIL",
    (2, 3, 7, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 3, 7, 2, "missing", "r3"): "FAIL",
    (2, 3, 7, 2, "missing", "r4"): "PASS",
    (2, 3, 7, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 7, 2, "none", "r1"): "FAIL",
    (2, 3, 7, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 3, 7, 2, "none", "r3"): "FAIL",
    (2, 3, 7, 2, "none", "r4"): "PASS",
    (2, 3, 7, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 7, 4, "missing", "r1"): "FAIL",
    (2, 3, 7, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 3, 7, 4, "missing", "r3"): "FAIL",
    (2, 3, 7, 4, "missing", "r4"): "PASS",
    (2, 3, 7, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 7, 4, "none", "r1"): "FAIL",
    (2, 3, 7, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 3, 7, 4, "none", "r3"): "FAIL",
    (2, 3, 7, 4, "none", "r4"): "PASS",
    (2, 3, 7, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 7, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 7, 6, "missing", "r2"): "PASS",
    (2, 3, 7, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 3, 7, 6, "missing", "r4"): "PASS",
    (2, 3, 7, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 7, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 3, 7, 6, "none", "r2"): "PASS",
    (2, 3, 7, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 3, 7, 6, "none", "r4"): "PASS",
    (2, 3, 7, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 7, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 7, 7, "missing", "r2"): "PASS",
    (2, 3, 7, 7, "missing", "r3"): "PASS",
    (2, 3, 7, 7, "missing", "r4"): "PASS",
    (2, 3, 7, 7, "missing", "r5"): "PASS",
    (2, 3, 7, 7, "none", "r1"): "PASS",
    (2, 3, 7, 7, "none", "r2"): "PASS",
    (2, 3, 7, 7, "none", "r3"): "PASS",
    (2, 3, 7, 7, "none", "r4"): "PASS",
    (2, 3, 7, 7, "none", "r5"): "PASS",
    (2, 3, 7, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 7, 8, "missing", "r2"): "PASS",
    (2, 3, 7, 8, "missing", "r3"): "PASS",
    (2, 3, 7, 8, "missing", "r4"): "PASS",
    (2, 3, 7, 8, "missing", "r5"): "PASS",
    (2, 3, 7, 8, "none", "r1"): "PASS",
    (2, 3, 7, 8, "none", "r2"): "PASS",
    (2, 3, 7, 8, "none", "r3"): "PASS",
    (2, 3, 7, 8, "none", "r4"): "PASS",
    (2, 3, 7, 8, "none", "r5"): "PASS",
    (2, 3, 7, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 7, 9, "missing", "r2"): "PASS",
    (2, 3, 7, 9, "missing", "r3"): "PASS",
    (2, 3, 7, 9, "missing", "r4"): "PASS",
    (2, 3, 7, 9, "missing", "r5"): "PASS",
    (2, 3, 7, 9, "none", "r1"): "PASS",
    (2, 3, 7, 9, "none", "r2"): "PASS",
    (2, 3, 7, 9, "none", "r3"): "PASS",
    (2, 3, 7, 9, "none", "r4"): "PASS",
    (2, 3, 7, 9, "none", "r5"): "PASS",
    (2, 3, 8, 2, "missing", "r1"): "FAIL",
    (2, 3, 8, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 3, 8, 2, "missing", "r3"): "FAIL",
    (2, 3, 8, 2, "missing", "r4"): "PASS",
    (2, 3, 8, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 8, 2, "none", "r1"): "FAIL",
    (2, 3, 8, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 3, 8, 2, "none", "r3"): "FAIL",
    (2, 3, 8, 2, "none", "r4"): "PASS",
    (2, 3, 8, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 8, 4, "missing", "r1"): "FAIL",
    (2, 3, 8, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 3, 8, 4, "missing", "r3"): "FAIL",
    (2, 3, 8, 4, "missing", "r4"): "PASS",
    (2, 3, 8, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 8, 4, "none", "r1"): "FAIL",
    (2, 3, 8, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 3, 8, 4, "none", "r3"): "FAIL",
    (2, 3, 8, 4, "none", "r4"): "PASS",
    (2, 3, 8, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 8, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 8, 6, "missing", "r2"): "PASS",
    (2, 3, 8, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 3, 8, 6, "missing", "r4"): "PASS",
    (2, 3, 8, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 8, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 3, 8, 6, "none", "r2"): "PASS",
    (2, 3, 8, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 3, 8, 6, "none", "r4"): "PASS",
    (2, 3, 8, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 8, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 8, 7, "missing", "r2"): "PASS",
    (2, 3, 8, 7, "missing", "r3"): "PASS",
    (2, 3, 8, 7, "missing", "r4"): "PASS",
    (2, 3, 8, 7, "missing", "r5"): "PASS",
    (2, 3, 8, 7, "none", "r1"): "PASS",
    (2, 3, 8, 7, "none", "r2"): "PASS",
    (2, 3, 8, 7, "none", "r3"): "PASS",
    (2, 3, 8, 7, "none", "r4"): "PASS",
    (2, 3, 8, 7, "none", "r5"): "PASS",
    (2, 3, 8, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 8, 8, "missing", "r2"): "PASS",
    (2, 3, 8, 8, "missing", "r3"): "PASS",
    (2, 3, 8, 8, "missing", "r4"): "PASS",
    (2, 3, 8, 8, "missing", "r5"): "PASS",
    (2, 3, 8, 8, "none", "r1"): "PASS",
    (2, 3, 8, 8, "none", "r2"): "PASS",
    (2, 3, 8, 8, "none", "r3"): "PASS",
    (2, 3, 8, 8, "none", "r4"): "PASS",
    (2, 3, 8, 8, "none", "r5"): "PASS",
    (2, 3, 8, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 8, 9, "missing", "r2"): "PASS",
    (2, 3, 8, 9, "missing", "r3"): "PASS",
    (2, 3, 8, 9, "missing", "r4"): "PASS",
    (2, 3, 8, 9, "missing", "r5"): "PASS",
    (2, 3, 8, 9, "none", "r1"): "PASS",
    (2, 3, 8, 9, "none", "r2"): "PASS",
    (2, 3, 8, 9, "none", "r3"): "PASS",
    (2, 3, 8, 9, "none", "r4"): "PASS",
    (2, 3, 8, 9, "none", "r5"): "PASS",
    (2, 3, 9, 2, "missing", "r1"): "FAIL",
    (2, 3, 9, 2, "missing", "r2"): "INCONCLUSIVE",
    (2, 3, 9, 2, "missing", "r3"): "FAIL",
    (2, 3, 9, 2, "missing", "r4"): "PASS",
    (2, 3, 9, 2, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 9, 2, "none", "r1"): "FAIL",
    (2, 3, 9, 2, "none", "r2"): "INCONCLUSIVE",
    (2, 3, 9, 2, "none", "r3"): "FAIL",
    (2, 3, 9, 2, "none", "r4"): "PASS",
    (2, 3, 9, 2, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 9, 4, "missing", "r1"): "FAIL",
    (2, 3, 9, 4, "missing", "r2"): "INCONCLUSIVE",
    (2, 3, 9, 4, "missing", "r3"): "FAIL",
    (2, 3, 9, 4, "missing", "r4"): "PASS",
    (2, 3, 9, 4, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 9, 4, "none", "r1"): "FAIL",
    (2, 3, 9, 4, "none", "r2"): "INCONCLUSIVE",
    (2, 3, 9, 4, "none", "r3"): "FAIL",
    (2, 3, 9, 4, "none", "r4"): "PASS",
    (2, 3, 9, 4, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 9, 6, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 9, 6, "missing", "r2"): "PASS",
    (2, 3, 9, 6, "missing", "r3"): "INCONCLUSIVE",
    (2, 3, 9, 6, "missing", "r4"): "PASS",
    (2, 3, 9, 6, "missing", "r5"): "INCONCLUSIVE",
    (2, 3, 9, 6, "none", "r1"): "INCONCLUSIVE",
    (2, 3, 9, 6, "none", "r2"): "PASS",
    (2, 3, 9, 6, "none", "r3"): "INCONCLUSIVE",
    (2, 3, 9, 6, "none", "r4"): "PASS",
    (2, 3, 9, 6, "none", "r5"): "INCONCLUSIVE",
    (2, 3, 9, 7, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 9, 7, "missing", "r2"): "PASS",
    (2, 3, 9, 7, "missing", "r3"): "PASS",
    (2, 3, 9, 7, "missing", "r4"): "PASS",
    (2, 3, 9, 7, "missing", "r5"): "PASS",
    (2, 3, 9, 7, "none", "r1"): "PASS",
    (2, 3, 9, 7, "none", "r2"): "PASS",
    (2, 3, 9, 7, "none", "r3"): "PASS",
    (2, 3, 9, 7, "none", "r4"): "PASS",
    (2, 3, 9, 7, "none", "r5"): "PASS",
    (2, 3, 9, 8, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 9, 8, "missing", "r2"): "PASS",
    (2, 3, 9, 8, "missing", "r3"): "PASS",
    (2, 3, 9, 8, "missing", "r4"): "PASS",
    (2, 3, 9, 8, "missing", "r5"): "PASS",
    (2, 3, 9, 8, "none", "r1"): "PASS",
    (2, 3, 9, 8, "none", "r2"): "PASS",
    (2, 3, 9, 8, "none", "r3"): "PASS",
    (2, 3, 9, 8, "none", "r4"): "PASS",
    (2, 3, 9, 8, "none", "r5"): "PASS",
    (2, 3, 9, 9, "missing", "r1"): "INCONCLUSIVE",
    (2, 3, 9, 9, "missing", "r2"): "PASS",
    (2, 3, 9, 9, "missing", "r3"): "PASS",
    (2, 3, 9, 9, "missing", "r4"): "PASS",
    (2, 3, 9, 9, "missing", "r5"): "PASS",
    (2, 3, 9, 9, "none", "r1"): "PASS",
    (2, 3, 9, 9, "none", "r2"): "PASS",
    (2, 3, 9, 9, "none", "r3"): "PASS",
    (2, 3, 9, 9, "none", "r4"): "PASS",
    (2, 3, 9, 9, "none", "r5"): "PASS",
}


MATRIX_RULES = [
    "recruiter | PASS if score at least 7 in 6 of 6; FAIL if score at most 4 in 2 or more; "
    "otherwise INCONCLUSIVE",
    "recruiter | PASS if score at least 6 in 2 or more; otherwise INCONCLUSIVE",
    "manager | FAIL if score at most 4 in 2 or more; PASS if score at least 7 in 3 or more; "
    "otherwise INCONCLUSIVE",
    "manager | PASS if DOUBTS not flagged in 3 or more; otherwise INCONCLUSIVE",
    "overall | PASS if score at least 7 in 6 or more; otherwise INCONCLUSIVE",
]
HEADROOM_REASONS = ("no headroom", "headroom not assessed")
# How many of the 1080 verdicts of the matrix revision 4 keeps, and how many were a PASS that
# headroom makes INCONCLUSIVE.
KEPT, LOST_TO_HEADROOM = 795, 285


class FailOpenCase(unittest.TestCase):
    def test_revision_3_verdicts_are_kept_or_lose_a_pass_to_headroom(self):
        self.assertEqual(len(REV3), 1080)
        kept, lost, plans = 0, 0, 0
        for readers, anchor, strong, version, missing in itertools.product(
                (1, 2), (1, 2, 3), (7, 8, 9), (2, 4, 6, 7, 8, 9), ("none", "missing")):
            fake = ["all | weak | score 2", "all | strong | score %d" % strong,
                    "all | version | score %d" % version]
            if missing == "missing":
                fake.append("recruiter | version | omit SCORE | read %d" % (2 * readers * anchor
                                                                          + 1))
            with self.subTest(readers=readers, anchor=anchor, strong=strong, version=version,
                              missing=missing):
                s = Setup(self, readers=["r%d | fake" % (n + 1) for n in range(readers)],
                          anchor_reads_per_reader=str(anchor), rules=list(MATRIX_RULES),
                          fake_reader=fake,
                          min_valid_reads="2" if missing == "missing" else None)
                result = s.frozen_run()
                self.assertIn(result.exit_code, (0, 1), result.error)
                plans += 1
                lines = s.result_lines()
                for name in ("r1", "r2", "r3", "r4", "r5"):
                    verdict = [x.split(" verdict: ")[1].split(" [")[0] for x in lines
                               if x.startswith("rule %s (" % name) and " verdict: " in x]
                    reasons = [x.split(" reason: ", 1)[1] for x in lines
                               if x.startswith("rule %s (" % name) and " reason: " in x]
                    self.assertEqual(len(verdict), 1)
                    before = REV3[(readers, anchor, strong, version, missing, name)]
                    if verdict[0] == before:
                        kept += 1
                    else:
                        self.assertEqual((before, verdict[0]), ("PASS", "INCONCLUSIVE"))
                        self.assertEqual(len(reasons), 1, reasons)
                        self.assertTrue(reasons[0].startswith(HEADROOM_REASONS), reasons)
                        lost += 1
        self.assertEqual(plans, 216)
        self.assertEqual((kept, lost), (KEPT, LOST_TO_HEADROOM))


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PROMPT_ABC = """You are reading one career document for a job, in the role that
LENS.txt gives you. You know nothing about the candidate beyond what is
in these files. Do not guess or use outside knowledge.

Your folder holds four files:
  LENS.txt      the role you read in, and what that role looks for
  POSTING.txt   the job posting
  DOCUMENT.txt  the document to read
  PROMPT.txt    this text

Nothing tells you whether this document is a draft, a final version or a
sample. Judge it on its own, against the posting, in your role.

Read LENS.txt, then the posting, then the document. Answer on standard
output only. Write these 11 fields, in this order, each starting its
own line as FIELD: value. No bullets, bold, indentation or text before
the first field or after the last. A value may continue on later lines;
the next field name starts a new line.

READ: anything; this value is not checked
PRIOR: what you knew about the candidate before reading. If nothing, write exactly: nothing
CRITERION-a: a whole number, as digits only, for the criterion a, on the scale LENS.txt gives
CRITERION-b: a whole number, as digits only, for the criterion b, on the scale LENS.txt gives
CRITERION-c: a whole number, as digits only, for the criterion c, on the scale LENS.txt gives
STRENGTHS: what in the document works for this role; write exactly `none` if you have nothing material.
DOUBTS: what made you doubt the candidate; write exactly `none` if you have nothing material.
UNDERSOLD: what the candidate has but did not make the most of; write exactly `none` if you have nothing material.
OVEREXPLAINED: what took more space or words than it earned; write exactly `none` if you have nothing material.
OWNED: what the candidate clearly did or led themselves; write exactly `none` if you have nothing material.
FLAG-FIXES: changes you would suggest, as text only; nothing is applied; write exactly `none` if you have nothing material.
"""


if __name__ == "__main__":
    unittest.main()
