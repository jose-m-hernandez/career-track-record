"""Tests for Reader A/B (career_track_record.ab). All data here is invented.

Every plan in these tests is written as plan text, in the syntax of docs/specs/reader-ab.md,
and read by ``ab.parse``; a test names only the lines it changes from the default plan.
Each test builds its run folder in a fresh temporary folder from the fixtures in
tests/fixtures/ab; nothing is ever written into tests/fixtures. The test numbers (10.1 and
so on) are those of docs/specs/reader-ab.md, section 10 and its revision 1.1 additions.
"""

import hashlib
import os
import shlex
import shutil
import stat
import sys
import tempfile
import unittest
from fractions import Fraction
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "ab")
sys.path.insert(0, SRC)

from career_track_record import ab  # noqa: E402

FIXTURES = ("base.txt", "skills-top.txt", "skills-top-short.txt", "posting.txt")
GLANCE = "At a glance"
SYSTEM_PATH = "/usr/bin:/bin"

VERSIONS = ["base | base.txt", "skills-top | skills-top.txt",
            "skills-top-short | skills-top-short.txt"]
SCOPE = ["^Skills$", "^At a glance$", "^Languages:", "^Tools:", "^Practices:"]
SIX = ("SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; "
       "otherwise INCONCLUSIVE")
SIX_RULE = "SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more"
SHORT_SIX = "SUPPORTED if skills-top-short preferred in 6 of 6; otherwise INCONCLUSIVE"
TWO = ["base vs skills-top", "base vs skills-top-short"]
PREFER_GLANCE = 'prefer containing "At a glance"'
WITHOUT_GLANCE = 'prefer without "At a glance"'
TOO_LONG = "too long | default | supported at 3 or more"
WRITE_TOO_LONG = 'write "too long" in DOUBTS'


def default_values():
    """The default plan of the spec (section 10): one comparison, two readers with 3 reads
    each, the default noise threshold, and the fake reader's default TIE."""
    return dict(
        posting="posting.txt",
        versions=list(VERSIONS),
        comparisons=["base vs skills-top"],
        aa_version="skills-top",
        readers=["r1 | fake", "r2 | fake"],
        reads_per_reader="3",
        noise_threshold="1/2",
        change_scope=list(SCOPE),
    )


def plan_text(values):
    """Plan text for a dict of values: a list becomes indented items, a string one value, and
    None leaves the key out. A key's underscores are written as hyphens."""
    out = ["# a plan for the tests\n"]
    for key, value in values.items():
        if value is None:
            continue
        name = key.replace("_", "-")
        if isinstance(value, (list, tuple)):
            out.append("%s:\n" % name)
            out.extend("  %s\n" % item for item in value)
        else:
            out.append("%s: %s\n" % (name, value))
    return "".join(out)


def items(rule, reads=(), arm=None, strength=None):
    """Fake-reader items for one rule: one per read number, or one for every read."""
    base = rule if arm is None else "%s | %s" % (arm, rule)
    if strength is not None:
        base += " | " + strength
    if not reads:
        return [base]
    return ["%s | read %d" % (base, number) for number in reads]


class Setup(object):
    """A run folder in a fresh temporary folder, holding the four fixtures and a plan file
    written from the default values with keyword overrides."""

    def __init__(self, case, **overrides):
        self._tmp = tempfile.TemporaryDirectory()
        case.addCleanup(self._tmp.cleanup)
        self.case = case
        self.folder = self._tmp.name
        for name in FIXTURES:
            shutil.copyfile(os.path.join(FX, name), os.path.join(self.folder, name))
        self.plan_path = os.path.join(self.folder, "plan.txt")
        self.values = default_values()
        self.change(**overrides)

    def change(self, **overrides):
        """Rewrite the plan file with changed values (before the freeze)."""
        self.values.update(overrides)
        self.write("plan.txt", plan_text(self.values))

    @property
    def plan(self):
        return ab.parse(self.plan_path)

    def line_of(self, text):
        """The 1-based line number in the plan of the first line that holds ``text``."""
        for number, line in enumerate(self.read("plan.txt").split("\n"), 1):
            if text in line:
                return number
        raise AssertionError("not in the plan: %r" % text)

    def path(self, *names):
        return os.path.join(self.folder, *names)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def read(self, *names):
        with open(self.path(*names), encoding="utf-8", newline="") as handle:
            return handle.read()

    def edit(self, name, change):
        self.write(name, change(self.read(name)))

    def exists(self, *names):
        return os.path.exists(self.path(*names))

    def freeze(self):
        return ab.freeze(self.plan_path)

    def run(self, live=False):
        return ab.run(self.plan_path, live=live)

    def score(self):
        return ab.score(self.plan_path)

    def frozen_run(self, live=False):
        frozen = self.freeze()
        self.case.assertEqual(frozen.exit_code, 0, frozen.error)
        return self.run(live=live)

    def result_names(self):
        return sorted(n for n in os.listdir(self.folder) if n.startswith(ab.RESULT_STEM))

    def result_lines(self, number=1):
        return self.read("%s%d.txt" % (ab.RESULT_STEM, number)).splitlines()

    def read_folder(self, arm, number):
        return self.path(ab.READS_DIR, arm, str(number))

    def reply_count(self, arm):
        folder = self.path(ab.READS_DIR, arm)
        if not os.path.isdir(folder):
            return 0
        return len([n for n in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, n, ab.READ_REPLY))])

    def tree_hashes(self):
        found = {}
        for folder, _dirs, names in os.walk(self.folder):
            for name in names:
                path = os.path.join(folder, name)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, self.folder)] = hashlib.sha256(
                        handle.read()).hexdigest()
        return found


def sha256_of(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def reword(text):
    """The text with one experience bullet reworded, and the line before and after."""
    old = next(line for line in text.split("\n") if "ninety" in line)
    new = old.replace("ninety", "eighty")
    return text.replace(old, new, 1), ab.collapsed_lines(old)[0], ab.collapsed_lines(new)[0]


class FreezeCase(unittest.TestCase):
    def test_freeze_writes_one_hash_per_input(self):
        s = Setup(self)
        result = s.freeze()
        self.assertEqual((result.exit_code, result.ran, result.error), (0, True, ""))
        self.assertEqual(result.text, "freeze written: plan.txt.freeze\n")
        expected = ["%s  %s" % (sha256_of(s.path(name)), name) for name in (
            "plan.txt", "posting.txt", "base.txt", "skills-top.txt", "skills-top-short.txt")]
        expected.append("%s  %s" % (ab.prompt_sha256(), ab.PROMPT_LABEL))
        self.assertEqual(s.read("plan.txt.freeze").splitlines(), expected)

    def test_freeze_refuses_a_missing_input_and_writes_nothing(self):
        s = Setup(self)
        os.remove(s.path("posting.txt"))
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), ["missing input: posting.txt"])
        self.assertFalse(s.exists("plan.txt.freeze"))

    def test_10_6_version_edited_after_freeze_exits_2(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        # Trailing blanks change the file's hash and nothing the isolation check sees.
        s.edit("skills-top.txt", lambda text: text + "   \n")
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["changed since the freeze: skills-top.txt"])
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertFalse(s.exists(ab.KEY_FILE))
        self.assertEqual(s.result_names(), [])

    def test_10_7_freeze_over_a_reply_is_refused(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        os.remove(s.path("plan.txt.freeze"))
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("the run folder already holds a reply: reads/aa/1/REPLY.txt",
                      result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))

    def test_10_17_freeze_over_a_freeze_is_refused(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        before = s.read("plan.txt.freeze")
        again = s.freeze()
        self.assertEqual(again.exit_code, 2)
        self.assertEqual(again.error.splitlines(),
                         ["a freeze file already exists: plan.txt.freeze"])
        self.assertEqual(s.read("plan.txt.freeze"), before)
        # Any freeze file in the folder counts, whatever the plan is called.
        s.write("other-plan.txt", s.read("plan.txt"))
        other = ab.freeze(s.path("other-plan.txt"))
        self.assertEqual(other.exit_code, 2)
        self.assertEqual(other.error.splitlines(),
                         ["a freeze file already exists: plan.txt.freeze"])
        self.assertFalse(s.exists("other-plan.txt.freeze"))

    def test_10_18_amendment_names_both_freezes(self):
        first = Setup(self)
        self.assertEqual(first.frozen_run().exit_code, 0)
        first_hashes = first.tree_hashes()
        first_freeze = sha256_of(first.path("plan.txt.freeze"))
        second = Setup(self, amends=first.path("plan.txt.freeze"))
        self.assertEqual(second.freeze().exit_code, 0)
        self.assertIn("%s  %s" % (first_freeze, first.path("plan.txt.freeze")),
                      second.read("plan.txt.freeze").splitlines())
        ran = second.run()
        self.assertEqual(ran.exit_code, 0, ran.error)
        self.assertEqual(second.score().exit_code, 0)
        second_freeze = sha256_of(second.path("plan.txt.freeze"))
        for number in (1, 2):
            lines = second.result_lines(number)
            self.assertIn("freeze sha256: " + second_freeze, lines)
            self.assertIn("amended freeze sha256: " + first_freeze, lines)
        self.assertEqual(first.tree_hashes(), first_hashes)
        refused = first.freeze()
        self.assertEqual(refused.exit_code, 2)
        replies = ["the run folder already holds a reply: reads/%s/%s/%s"
                   % (arm, number, ab.READ_REPLY)
                   for arm in sorted(os.listdir(first.path(ab.READS_DIR)))
                   for number in sorted(os.listdir(first.path(ab.READS_DIR, arm)))]
        self.assertEqual(len(replies), 12)
        self.assertEqual(refused.error.splitlines(),
                         ["a freeze file already exists: plan.txt.freeze"] + replies)
        self.assertEqual(first.tree_hashes(), first_hashes)

    def test_10_19_aa_arm_added_and_no_comparison_exits_2_a(self):
        s = Setup(self, aa_version=None)
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertIn("A/A arm: added by the tool, using version skills-top",
                      s.result_lines())
        self.assertIn("A/A version: the default, the second version of the first comparison",
                      s.result_lines())
        self.assertEqual(s.reply_count("aa"), 6)
        named = Setup(self)
        self.assertEqual(named.frozen_run().exit_code, 0)
        self.assertIn("A/A arm: added by the tool, using version skills-top",
                      named.result_lines())
        self.assertIn("A/A version: named by aa-version in the plan", named.result_lines())
        # The default A/A version is the second version of the first comparison.
        other = Setup(self, aa_version=None, comparisons=["skills-top vs base"])
        self.assertEqual(other.frozen_run().exit_code, 0)
        self.assertIn("A/A arm: added by the tool, using version base", other.result_lines())

    def test_10_19_aa_arm_added_and_no_comparison_exits_2_b(self):
        s = Setup(self, comparisons=[])
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), ["the plan has no comparison"])
        # run and score rely on the freeze, so with no freeze they find none.
        for call in (s.run, s.score):
            result = call()
            self.assertEqual(result.exit_code, 2)
            self.assertEqual(result.error.splitlines(), ["no freeze file: plan.txt.freeze"])
        self.assertFalse(s.exists("plan.txt.freeze"))
        self.assertFalse(s.exists(ab.READS_DIR))

    def test_10_28_plan_edited_after_freeze_exits_2(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        s.write("plan.txt", "# plan for 10.28, edited\n")
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), ["changed since the freeze: plan.txt"])
        self.assertFalse(s.exists(ab.READS_DIR))

    def test_a_posting_edited_after_freeze_is_named(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        s.edit("posting.txt", lambda text: text + "\n")
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), ["changed since the freeze: posting.txt"])

    def test_every_changed_file_is_named(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        s.write("plan.txt", "# edited\n")
        s.edit("base.txt", lambda text: text + " \n")
        s.edit("skills-top-short.txt", lambda text: text + " \n")
        self.assertEqual(s.run().error.splitlines(), [
            "changed since the freeze: plan.txt", "changed since the freeze: base.txt",
            "changed since the freeze: skills-top-short.txt"])

    def test_run_and_score_need_a_freeze(self):
        s = Setup(self)
        for call in (s.run, s.score):
            result = call()
            self.assertEqual(result.exit_code, 2)
            self.assertIn("no freeze file: plan.txt.freeze", result.error.splitlines())

    def test_score_checks_every_hash_first(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        s.edit("skills-top.txt", lambda text: text + " \n")
        result = s.score()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["changed since the freeze: skills-top.txt"])
        self.assertEqual(s.result_names(), ["result-1.txt"])

    def test_a_second_run_in_the_same_folder_is_refused(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        again = s.run()
        self.assertEqual(again.exit_code, 2)
        self.assertEqual(again.error.splitlines(), [
            "the run folder already holds a run: reads",
            "the run folder already holds a run: key.txt",
            "the run folder already holds a run: run-log.txt"])

    def test_12_a_prompt_that_differs_from_the_frozen_one_exits_2(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        with mock.patch.object(ab, "PROMPT", ab.PROMPT + "One more line.\n"):
            result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["changed since the freeze: PROMPT.txt (built into the tool)"])
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertFalse(s.exists(ab.KEY_FILE))

    def test_the_result_names_the_prompt_hash(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertIn("prompt sha256: " + ab.prompt_sha256(), s.result_lines())
        self.assertIn("%s  %s" % (ab.prompt_sha256(), ab.PROMPT_LABEL),
                      s.read("plan.txt.freeze").splitlines())

    def test_a_live_reader_is_not_a_plan_error(self):
        s = Setup(self, readers=["r1 | fake", "r2 | python3 stub.py | cost 3"])
        result = s.freeze()
        self.assertEqual((result.exit_code, result.error), (0, ""))


# ------------------------------------------------------------------ the plan file

EXAMPLE_PLAN = """\
versions:
  base | base.txt
  skills-top | skills-top.txt
comparisons:
  base vs skills-top
readers:
  reader-1 | fake
  reader-2 | /path/to/my-reader.sh --model small | not-blind | cost 3
hypotheses:
  base vs skills-top | SUPPORTED if skills-top preferred in 6 of 6; REFUTED if base preferred in 4 or more; otherwise INCONCLUSIVE
mechanisms:
  too long | default | supported at 3 or more
change-scope:
  ^(Skills|At a glance)
fake-reader:
  aa | prefer slot A | slightly
"""


class PlanFileCase(unittest.TestCase):
    def assertRefused(self, s, line_text, message):
        """Freeze exits 2, names the plan line number, and writes no freeze file."""
        result = s.freeze()
        self.assertEqual(result.exit_code, 2, result.error)
        self.assertFalse(result.ran)
        number = s.line_of(line_text)
        self.assertIn("plan line %d: %s" % (number, message), result.error.splitlines())
        self.assertFalse(s.exists("plan.txt.freeze"))
        self.assertFalse(s.exists(ab.READS_DIR))

    def test_the_example_of_the_spec_is_read_as_written(self):
        plan = ab.parse_text(EXAMPLE_PLAN + "posting: posting.txt\n")
        self.assertEqual(plan.versions, [("base", "base.txt"), ("skills-top", "skills-top.txt")])
        self.assertEqual(plan.comparisons, [("base", "skills-top")])
        self.assertEqual([(r.name, r.command, r.not_blind, r.cost, r.kind)
                          for r in plan.readers],
                         [("reader-1", "fake", False, 1, "fake"),
                          ("reader-2", "/path/to/my-reader.sh --model small", True, 3, "live")])
        hyp = plan.hypotheses[0]
        self.assertEqual((hyp.name, hyp.comparison), ("h1", 1))
        self.assertEqual([(kind, c.version, c.k, c.n) for kind, c in hyp.clauses],
                         [("SUPPORTED", "skills-top", 6, 6), ("REFUTED", "base", 4, None)])
        mech = plan.mechanisms[0]
        self.assertEqual((mech.name, mech.comparison, mech.pattern, mech.k, mech.fields),
                         ("too long", 1, "too long", 3, ab.FREE_TEXT_FIELDS))
        self.assertEqual(plan.change_scope, [(None, "^(Skills|At a glance)")])
        rule = plan.fake_rules[0]
        self.assertEqual((rule.kind, rule.slot, rule.strength, rule.arms),
                         ("slot", "A", "slightly", frozenset(["aa"])))

    def test_defaults(self):
        plan = ab.parse_text("posting: p.txt\nversions:\n  a | a.txt\n  b | b.txt\n"
                             "comparisons:\n  a vs b\nreaders:\n  r | fake\n")
        self.assertEqual((plan.reads_per_reader, plan.noise_threshold, plan.spend_ceiling,
                          plan.read_timeout, plan.aa_version, plan.amends),
                         (3, Fraction(1, 2), None, 600, None, None))
        self.assertEqual(plan.effective_aa_version(), "b")
        self.assertEqual(plan.change_scope, [])

    def test_scalar_values(self):
        s = Setup(self, noise_threshold="1/3", spend_ceiling="12", read_timeout="30",
                  reads_per_reader="2")
        plan = s.plan
        self.assertEqual((plan.noise_threshold, plan.spend_ceiling, plan.read_timeout,
                          plan.reads_per_reader), (Fraction(1, 3), 12, 30, 2))

    def test_comments_and_blank_lines_are_ignored(self):
        s = Setup(self)
        s.write("plan.txt", "# one\n\n   # two\n" + s.read("plan.txt") + "\n\n# end\n")
        self.assertEqual(s.freeze().exit_code, 0)

    def test_10_32_bar_inside_a_field_is_refused(self):
        s = Setup(self, change_scope=["^(Skills | At a glance)$"])
        self.assertRefused(s, "At a glance)", "a change-scope item is written: "
                           "[comparison |] pattern")
        t = Setup(self, versions=VERSIONS + ["odd | my | file.txt"])
        self.assertRefused(t, "my | file.txt", "a version is written: name | file")
        u = Setup(self, mechanisms=["a | b | default | supported at 3 or more"])
        self.assertRefused(u, "a | b |", "a mechanism is written: [comparison |] pattern | "
                           "fields | supported at <n> or more")

    def test_10_33_missing_comparison_field_is_refused(self):
        s = Setup(self, comparisons=TWO, hypotheses=[SIX])
        self.assertRefused(s, "SUPPORTED if", "a hypothesis must start with its comparison, "
                           "written as in comparisons")
        t = Setup(self, comparisons=TWO, mechanisms=[TOO_LONG])
        self.assertRefused(t, "too long", "a mechanism must start with its comparison, "
                           "written as in comparisons")

    def test_a_change_scope_item_without_a_comparison_is_allowed_with_two(self):
        s = Setup(self, comparisons=TWO)
        self.assertEqual(s.freeze().exit_code, 0)

    def test_10_34_two_preference_rules_on_one_read_are_refused(self):
        s = Setup(self, fake_reader=["all | prefer slot A", "base vs skills-top | tie"])
        self.assertRefused(s, "base vs skills-top | tie",
                           "two preference rules apply to read 1 of c1 (the other is on "
                           "line %d)" % s.line_of("all | prefer slot A"))

    def test_preference_rules_that_never_meet_are_allowed(self):
        s = Setup(self, comparisons=TWO, fake_reader=[
            "all | prefer slot A | read 1", "all | prefer slot B | read 2",
            "aa | prefer slot A", "base vs skills-top | prefer slot B | read 3",
            items(PREFER_GLANCE, reads=[4], arm="base vs skills-top-short")[0],
            'write "x" in DOUBTS', "omit OWNED", "score 1 2"])
        self.assertEqual(s.freeze().exit_code, 0)

    def test_every_plan_error_is_found_by_freeze_with_its_line(self):
        cases = [
            (dict(readers=["r1 | fake"], fake_reader=["prefer slot A | read 7"]),
             "read 7", "read 7 is outside the arm's reads (1 to 3)"),
            (dict(hypotheses=["SUPPORTED if skills-top-short preferred in 6 of 6; "
                              "otherwise INCONCLUSIVE"]),
             "skills-top-short preferred",
             "the hypothesis names skills-top-short, which is not in its comparison"),
            (dict(hypotheses=["SUPPORTED if skills-top preferred in 7 of 6; "
                              "otherwise INCONCLUSIVE"]),
             "7 of 6", "7 of 6 asks for more reads than it counts"),
            (dict(hypotheses=["SUPPORTED if skills-top preferred in 6 of 6"]),
             "6 of 6", "a hypothesis rule ends with: otherwise INCONCLUSIVE"),
            (dict(hypotheses=["otherwise INCONCLUSIVE"]),
             "otherwise", "a hypothesis rule needs at least one SUPPORTED or REFUTED clause"),
            (dict(readers=["r_1 | fake"]), "r_1", "a name holds letters, digits and - only: r_1"),
            (dict(versions=VERSIONS + ["base | other.txt"]), "base | other.txt",
             "the version base is named twice"),
            (dict(versions=VERSIONS + ["bad name | x.txt"]), "bad name",
             "a name holds letters, digits and - only: bad name"),
            (dict(comparisons=["base vs nobody"]), "nobody",
             "a comparison names a version the plan does not have"),
            (dict(aa_version="nobody"), "aa-version", "aa-version names the unknown version "
             "nobody"),
            (dict(reads_per_reader="0"), "reads-per-reader",
             "reads-per-reader must be a positive whole number"),
            (dict(noise_threshold="0.5"), "noise-threshold",
             "noise-threshold is written as a fraction n/d"),
            (dict(noise_threshold="1/0"), "noise-threshold",
             "noise-threshold is written as a fraction n/d"),
            (dict(spend_ceiling="-1"), "spend-ceiling",
             "spend-ceiling must be a whole number, 0 or more"),
            (dict(read_timeout="soon"), "read-timeout",
             "read-timeout must be a whole number, 0 or more"),
            (dict(readers=["r1 | fake | cost lots"]), "cost lots",
             "cost must be a whole number, 0 or more"),
            (dict(readers=["r1 | fake | cheap"]), "cheap",
             "a reader's extra field is not-blind or cost <n>, once each: cheap"),
            (dict(readers=["r1 | 'unbalanced"]), "unbalanced",
             "the reader command cannot be split into words"),
            (dict(change_scope=["("]), "(", "not a valid pattern: ("),
            (dict(mechanisms=["( | default | supported at 3 or more"]), "( | default",
             "not a valid pattern: ("),
            (dict(mechanisms=["x | NOPE | supported at 3 or more"]), "NOPE",
             "not a reply field a pattern can match: NOPE"),
            (dict(mechanisms=["x | default | supported at zero or more"]), "zero",
             "the last field is: supported at <n> or more"),
            (dict(fake_reader=["tie | slightly"]), "tie | slightly", "tie takes no strength"),
            (dict(fake_reader=["prefer slot C"]), "slot C", "not a fake-reader rule: "
             "prefer slot C"),
            (dict(fake_reader=["write \"x\" in NOPE"]), "NOPE", "not a reply field: NOPE"),
            (dict(fake_reader=["omit NOPE"]), "omit NOPE", "not a reply field: NOPE"),
            (dict(fake_reader=["prefer slot A | loudly"]), "loudly",
             "after the rule come [| strength] [| read <k>]: loudly"),
            (dict(fake_reader=["prefer slot A | read 0"]), "read 0",
             "read 0 is outside the arm's reads (1 to 6)"),
        ]
        for overrides, text, message in cases:
            with self.subTest(message):
                s = Setup(self, **overrides)
                self.assertRefused(s, text, message)

    def test_duplicates_and_empty_fields(self):
        s = Setup(self, readers=["r1 | fake", "r1 | fake"])
        result = s.freeze()
        self.assertIn("plan line %d: the reader r1 is named twice" % (s.line_of("r1") + 1),
                      result.error.splitlines())
        t = Setup(self, comparisons=["base vs skills-top", "base vs skills-top"])
        self.assertIn("is named twice", t.freeze().error)
        u = Setup(self, versions=VERSIONS + ["x |  | y"])
        self.assertIn("an empty field", u.freeze().error)

    def test_fake_reader_items_with_no_fake_reader_are_refused(self):
        s = Setup(self, readers=["r1 | python3 stub.py"], fake_reader=["prefer slot A"])
        self.assertRefused(s, "prefer slot A", "fake-reader rules, but the plan has no fake "
                           "reader")

    def test_unknown_key_and_structure_errors(self):
        s = Setup(self, colour="blue")
        self.assertRefused(s, "colour", "unknown key colour")
        t = Setup(self)
        t.write("plan.txt", t.read("plan.txt") + "stray line\n")
        self.assertRefused(t, "stray line", "not a key: value line")
        u = Setup(self)
        u.write("plan.txt", "  indented first\n" + u.read("plan.txt"))
        self.assertRefused(u, "indented first", "an indented line that belongs to no key")
        v = Setup(self)
        v.write("plan.txt", v.read("plan.txt") + "posting: again.txt\n")
        self.assertRefused(v, "again.txt", "the key posting is given twice")
        w = Setup(self)
        w.write("plan.txt", w.read("plan.txt") + "noise-threshold: 1/4\n")
        self.assertIn("is given twice", w.freeze().error)
        x = Setup(self)
        x.write("plan.txt", x.read("plan.txt") + "read-timeout: 5\n  more\n")
        self.assertRefused(x, "more", "read-timeout takes one value on its own line, "
                           "not a list")
        y = Setup(self)
        y.write("plan.txt", y.read("plan.txt") + "fake-reader: tie\n")
        self.assertRefused(y, "fake-reader: tie", "fake-reader is a list: write its items "
                           "on indented lines")

    def test_a_plan_that_names_nothing_lists_every_gap(self):
        result = ab.freeze(self._write_plan("# nothing\n"))
        self.assertEqual(result.error.splitlines(), [
            "the plan names no posting", "the plan names no version",
            "the plan has no comparison", "the plan has no reader"])

    def _write_plan(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "plan.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_an_unreadable_plan_is_named(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        missing = os.path.join(tmp.name, "plan.txt")
        self.assertEqual(ab.freeze(missing).error, "cannot read the plan: plan.txt")
        with open(missing, "wb") as handle:
            handle.write(b"\xff\xfe\n")
        self.assertEqual(ab.freeze(missing).error, "the plan is not valid UTF-8: plan.txt")

    def test_run_finds_no_syntax_error_only_the_changed_plan(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        s.write("plan.txt", "colour: blue\n")
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), ["changed since the freeze: plan.txt"])

    def test_reader_names_cost_and_flags_in_either_order(self):
        s = Setup(self, readers=["a | fake | not-blind", "b | python3 x.py | cost 3 | not-blind",
                                 "c | python3 x.py | not-blind | cost 0", "d | fake | cost 7"])
        got = [(r.name, r.not_blind, r.cost, r.kind) for r in s.plan.readers]
        self.assertEqual(got, [("a", True, 1, "fake"), ("b", True, 3, "live"),
                               ("c", True, 0, "live"), ("d", False, 1, "fake")])

    def test_hypothesis_forms(self):
        s = Setup(self, hypotheses=[
            "base vs skills-top | SUPPORTED if skills-top is preferred in 3 of 3; "
            "REFUTED if base preferred in 2 or more; SUPPORTED if skills-top is preferred "
            "in 1 or more; otherwise INCONCLUSIVE"])
        hyp = s.plan.hypotheses[0]
        self.assertEqual([(kind, c.version, c.k, c.n) for kind, c in hyp.clauses],
                         [("SUPPORTED", "skills-top", 3, 3), ("REFUTED", "base", 2, None),
                          ("SUPPORTED", "skills-top", 1, None)])

    def test_mechanism_fields_and_comparison(self):
        s = Setup(self, comparisons=TWO, mechanisms=[
            "base vs skills-top-short | jargon | DOUBTS, PREFER | supported at 2 or more"])
        mech = s.plan.mechanisms[0]
        self.assertEqual((mech.comparison, mech.fields), (2, ("DOUBTS", "PREFER")))

    def test_fake_reader_rule_grammar(self):
        def rule(item):
            s = Setup(self, comparisons=TWO, fake_reader=[item])
            return s.plan.fake_rules[0]

        r = rule('prefer containing "At a glance"')
        self.assertEqual((r.kind, r.text, r.arms, r.on_reads, r.strength),
                         ("containing", GLANCE, None, None, "slightly"))
        r = rule('aa | prefer without "At a glance" | clearly')
        self.assertEqual((r.kind, r.arms, r.strength), ("not-containing", frozenset(["aa"]),
                                                        "clearly"))
        r = rule("base vs skills-top-short | tie")
        self.assertEqual((r.kind, r.arms), ("tie", frozenset(["c2"])))
        r = rule("all | prefer slot B | strongly | read 2")
        self.assertEqual((r.kind, r.slot, r.strength, r.on_reads, r.arms),
                         ("slot", "B", "strongly", frozenset([2]), None))
        r = rule("aa | random seed 7 non-tie")
        self.assertEqual((r.kind, r.seed, r.non_tie), ("random", 7, True))
        r = rule("random seed -3 | read 5")
        self.assertEqual((r.kind, r.seed, r.non_tie), ("random", -3, False))
        r = rule('write "a, b" in DOUBTS | read 1')
        self.assertEqual((r.kind, r.field, r.text), ("write", "DOUBTS", "a, b"))
        r = rule("omit READ | read 3")
        self.assertEqual((r.kind, r.field, r.on_reads), ("omit", "READ", frozenset([3])))
        r = rule("score 7 -2 | read 4")
        self.assertEqual((r.kind, r.scores), ("score", (7, -2)))

    def test_a_strength_on_write_omit_and_score_is_ignored(self):
        s = Setup(self, fake_reader=['write "x" in DOUBTS | strongly', "omit OWNED | clearly",
                                     "score 1 2 | slightly"])
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.run().exit_code, 0)
        with open(os.path.join(s.read_folder("c1", 1), ab.READ_REPLY),
                  encoding="utf-8") as handle:
            reply = ab.parse_reply(handle.read())
        self.assertEqual((reply.choice, reply.strength, reply.fields["DOUBTS"],
                          reply.score_a, reply.score_b), ("TIE", None, "x", 1, 2))
        self.assertNotIn("OWNED", reply.fields)

    def test_omit_beats_a_write_to_the_same_field_in_a_plan(self):
        s = Setup(self, fake_reader=['write "x" in DOUBTS', "omit DOUBTS"])
        self.assertEqual(s.frozen_run().exit_code, 0)
        with open(os.path.join(s.read_folder("c1", 1), ab.READ_REPLY),
                  encoding="utf-8") as handle:
            self.assertNotIn("DOUBTS", ab.parse_reply(handle.read()).fields)


# ------------------------------------------------------------------ the isolation check

class IsolationCase(unittest.TestCase):
    def test_collapsing_and_changed_lines(self):
        self.assertEqual(ab.collapsed_lines("  a \t b  \r\n\r\n\t\nc\r\fd\n"),
                         ["a b", "c", "d"])
        self.assertEqual(ab.changed_lines(["a", "b", "c"], ["a", "x", "c"]),
                         [("-", "b"), ("+", "x")])
        self.assertEqual(ab.changed_lines(["a"], ["a"]), [])

    def test_the_moved_skills_block_shows_as_removed_and_added(self):
        base = ab.collapsed_lines(ab.read_text(os.path.join(FX, "base.txt")))
        top = ab.collapsed_lines(ab.read_text(os.path.join(FX, "skills-top.txt")))
        block = ["Languages: Python, Go, shell, SQL",
                 "Tools: Kubernetes, Terraform, Postgres, Prometheus",
                 "Practices: code review, incident response, runbooks, mentoring"]
        self.assertEqual(ab.changed_lines(base, top),
                         [("+", "At a glance")] + [("+", x) for x in block]
                         + [("-", "Skills")] + [("-", x) for x in block])

    def test_a_long_block_moved_past_a_short_one_shows_the_short_one_changed(self):
        # Known limit: only the text a block moves past is shown as changed when that text is
        # shorter than the block (docs/specs/reader-ab.md, Known limit: moved blocks).
        long_block = ["line %d" % n for n in range(10)]
        short = ["short one", "short two"]
        self.assertEqual(
            ab.changed_lines(long_block + short, short + long_block),
            [("+", "short one"), ("+", "short two"), ("-", "short one"), ("-", "short two")])

    def test_10_4_change_outside_scope_stops_before_reading(self):
        s = Setup(self)
        reworded, old, new = reword(s.read("skills-top.txt"))
        s.write("skills-top.txt", reworded)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "c1: changed line outside the change scope: - " + old,
            "c1: changed line outside the change scope: + " + new])
        self.assertNotEqual(old, new)
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertFalse(s.exists(ab.KEY_FILE))

    def test_10_5_file_compared_with_itself_exits_2(self):
        s = Setup(self, comparisons=["base vs base"])
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "c1 (base vs base): no changed line; a file compared with itself is the "
            "control, not a test"])
        self.assertFalse(s.exists(ab.READS_DIR))

    def test_10_20_whitespace_only_difference_is_identical(self):
        s = Setup(self, versions=VERSIONS + ["padded | padded.txt"],
                  comparisons=["skills-top vs padded"])
        text = s.read("skills-top.txt")
        padded = "\n\n".join(text.split("\n"))
        # Each step must change the text, or it would test nothing.
        for old, new in (("Python, Go", "Python,  Go"), ("Tools: ", "Tools:\t"),
                         ("Platform Engineer", "Platform  Engineer")):
            changed = padded.replace(old, new)
            self.assertNotEqual(changed, padded, old)
            padded = changed
        self.assertNotEqual(padded, text)
        s.write("padded.txt", padded)
        self.assertEqual(ab.changed_lines(ab.collapsed_lines(text),
                                          ab.collapsed_lines(padded)), [])
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "c1 (skills-top vs padded): no changed line; a file compared with itself is "
            "the control, not a test"])
        self.assertFalse(s.exists(ab.READS_DIR))

    def test_10_30_combined_causes_take_the_higher_code(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        reworded, old, new = reword(s.read("skills-top.txt"))
        s.write("skills-top.txt", reworded)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "changed since the freeze: skills-top.txt",
            "c1: changed line outside the change scope: - " + old,
            "c1: changed line outside the change scope: + " + new])
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertFalse(s.exists(ab.KEY_FILE))

    def test_an_unreadable_version_is_a_missing_input(self):
        s = Setup(self)
        with open(s.path("skills-top.txt"), "wb") as handle:
            handle.write(b"\xff\xfe not text\n")
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["cannot read skills-top.txt: not valid UTF-8"])

    def test_a_missing_version_at_run_time_is_named_once(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        os.remove(s.path("skills-top.txt"))
        self.assertEqual(s.run().error.splitlines(), ["missing input: skills-top.txt"])

    def test_change_scope_is_per_comparison_when_a_comparison_is_given(self):
        # Scope lines that start with a comparison cover only that comparison; a line
        # with no comparison covers every comparison.
        only_first = ["base vs skills-top | " + pattern for pattern in SCOPE]
        s = Setup(self, comparisons=TWO, change_scope=only_first)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), [
            "c2: changed line outside the change scope: + At a glance",
            "c2: changed line outside the change scope: + Languages: Python, Go, shell, SQL",
            "c2: changed line outside the change scope: - Skills",
            "c2: changed line outside the change scope: - Languages: Python, Go, shell, SQL",
            "c2: changed line outside the change scope: - Tools: Kubernetes, Terraform, "
            "Postgres, Prometheus",
            "c2: changed line outside the change scope: - Practices: code review, incident "
            "response, runbooks, mentoring"])
        both = only_first + ["base vs skills-top-short | " + pattern for pattern in SCOPE]
        t = Setup(self, comparisons=TWO, change_scope=both)
        self.assertEqual(t.frozen_run().exit_code, 0)
        mixed = ["base vs skills-top-short | " + pattern for pattern in SCOPE] + SCOPE[:]
        u = Setup(self, comparisons=TWO, change_scope=mixed)
        self.assertEqual(u.frozen_run().exit_code, 0)


# ------------------------------------------------------------------ PDF versions

def pdf_with_text(lines, per_page=45):
    """A PDF, built by hand, whose pages hold the given lines (ASCII only)."""
    def escaped(line):
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
               b"/Encoding /WinAnsiEncoding >>"]
    kids = []
    for index, page in enumerate(pages):
        page_number, stream_number = 4 + 2 * index, 5 + 2 * index
        kids.append("%d 0 R" % page_number)
        stream = "BT\n/F1 10 Tf\n12 TL\n40 780 Td\n"
        stream += "".join("(%s) '\n" % escaped(line) for line in page) + "ET\n"
        stream = stream.encode("latin-1")
        objects.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
                        "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
                        % stream_number).encode("ascii"))
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream")
    objects[1] = ("<< /Type /Pages /Kids [%s] /Count %d >>"
                  % (" ".join(kids), len(pages))).encode("ascii")
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    start = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, start)
    return out


def pdftotext_gate(found, environ):
    """Run the real-program leg if pdftotext is installed; fail in CI if not; else skip."""
    if found:
        return "run"
    if environ.get("GITHUB_ACTIONS") == "true":
        return "fail"
    return "skip"


PDF_VERSIONS = ["base | base.txt", "skills-top | skills-top.pdf",
                "skills-top-short | skills-top-short.txt"]


class PdfVersionCase(unittest.TestCase):
    def pdf_setup(self, **overrides):
        s = Setup(self, versions=PDF_VERSIONS, **overrides)
        with open(s.path("skills-top.pdf"), "wb") as handle:
            handle.write(pdf_with_text(s.read("skills-top.txt").split("\n")))
        return s

    def changes(self, s):
        base = ab.collapsed_lines(ab.read_text(s.path("base.txt")))
        top = ab.collapsed_lines(ab.read_text(s.path(s.plan.version_path("skills-top"))))
        return [("c1", mark, line) for mark, line in ab.changed_lines(base, top)]

    def compare_with_text(self, rules):
        pdf = self.pdf_setup(fake_reader=rules, hypotheses=[SIX])
        plain = Setup(self, fake_reader=rules, hypotheses=[SIX])
        self.assertEqual(pdf.plan.version_path("skills-top"), "skills-top.pdf")
        self.assertEqual(self.changes(pdf), self.changes(plain))
        self.assertNotEqual(self.changes(pdf), [])
        ran_pdf, ran_plain = pdf.frozen_run(), plain.frozen_run()
        self.assertEqual((ran_pdf.exit_code, ran_plain.exit_code), (0, 0))

        def scored(s):
            return [line for line in s.result_lines()
                    if line.split(" ", 1)[0] in ("scores", "hypothesis", "reads", "position")
                    or line.startswith("A/A")]
        self.assertEqual(scored(pdf), scored(plain))
        self.assertIn("hypothesis h1 verdict: SUPPORTED", scored(pdf))

    def test_10_29_pdf_version_matches_its_text(self):
        # Leg (i): a stand-in pdftotext prints the text file, so the equality is exact.
        with tempfile.TemporaryDirectory() as bin_dir:
            stand_in = os.path.join(bin_dir, "pdftotext")
            with open(stand_in, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nexec cat %s\n"
                             % shlex.quote(os.path.join(FX, "skills-top.txt")))
            os.chmod(stand_in, os.stat(stand_in).st_mode | stat.S_IXUSR | stat.S_IRUSR)
            with mock.patch.dict(os.environ, {"PATH": bin_dir + os.pathsep + SYSTEM_PATH}):
                self.compare_with_text([PREFER_GLANCE])

    def test_10_29_pdf_version_matches_its_text_with_the_real_program(self):
        gate = pdftotext_gate(shutil.which("pdftotext") is not None, os.environ)
        if gate == "skip":
            self.skipTest("pdftotext is not installed")
        if gate == "fail":
            self.fail("pdftotext is not installed in CI; install poppler-utils so the "
                      "real-program leg of 10.29 runs")
        self.compare_with_text([PREFER_GLANCE])

    def test_the_gate_runs_fails_or_skips(self):
        self.assertEqual(pdftotext_gate(True, {}), "run")
        self.assertEqual(pdftotext_gate(False, {"GITHUB_ACTIONS": "true"}), "fail")
        self.assertEqual(pdftotext_gate(False, {}), "skip")

    def test_an_unreadable_pdf_is_a_missing_input(self):
        s = self.pdf_setup()
        with open(s.path("skills-top.pdf"), "wb") as handle:
            handle.write(b"not a pdf\n")
        self.assertEqual(s.freeze().exit_code, 0)
        with tempfile.TemporaryDirectory() as bin_dir:
            stand_in = os.path.join(bin_dir, "pdftotext")
            with open(stand_in, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nexit 1\n")
            os.chmod(stand_in, os.stat(stand_in).st_mode | stat.S_IXUSR | stat.S_IRUSR)
            with mock.patch.dict(os.environ, {"PATH": bin_dir + os.pathsep + SYSTEM_PATH}):
                result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["cannot read skills-top.pdf: pdftotext failed"])
        self.assertFalse(s.exists(ab.READS_DIR))


# ------------------------------------------------------------------ the reply format

def reply_text(**changes):
    fields = [("READ", "c1/1"), ("PRIOR", "nothing"), ("SCORE-A", "7"), ("SCORE-B", "5"),
              ("PREFER", "A, slightly"), ("DROVE-IT", "x"), ("DOUBTS", "y"),
              ("UNDERSOLD", "z"), ("OVEREXPLAINED", "w"), ("OWNED", "v"),
              ("FLAG-FIXES", "u")]
    out = []
    for label, value in fields:
        key = label.replace("-", "_")
        if key in changes:
            value = changes[key]
        if value is not None:
            out.append("%s: %s\n" % (label, value))
    return "".join(out)


class ReplyParserCase(unittest.TestCase):
    def test_a_good_reply(self):
        reply = ab.parse_reply(reply_text(PREFER="B, strongly the summary is clearer"))
        self.assertIsNone(reply.failure)
        self.assertEqual((reply.read_id, reply.score_a, reply.score_b), ("c1/1", 7, 5))
        self.assertEqual((reply.choice, reply.strength), ("B", "strongly"))
        self.assertEqual(reply.rationale, "the summary is clearer")
        self.assertIsNone(reply.prior_flag)

    def test_a_tie_takes_no_strength_and_may_carry_a_rationale(self):
        reply = ab.parse_reply(reply_text(PREFER="TIE equally clear"))
        self.assertIsNone(reply.failure)
        self.assertEqual((reply.choice, reply.strength, reply.rationale),
                         ("TIE", None, "equally clear"))
        plain = ab.parse_reply(reply_text(PREFER="TIE"))
        self.assertEqual((plain.choice, plain.rationale), ("TIE", ""))

    def test_a_tie_with_a_word_after_it_is_a_tie_with_that_rationale(self):
        for value, rationale in (("TIE, slightly", "slightly"), ("TIE clearly", "clearly"),
                                 ("TIE: both read well", "both read well"),
                                 ("TIE; - equal", "equal"),
                                 ("TIE \u2013 equal", "equal"), ("TIE \u2014 equal", "equal"),
                                 ("TIE,, ; : - \u2013 \u2014 equal", "equal")):
            with self.subTest(value):
                reply = ab.parse_reply(reply_text(PREFER=value))
                self.assertIsNone(reply.failure)
                self.assertEqual((reply.choice, reply.strength, reply.rationale),
                                 ("TIE", None, rationale))

    def test_the_rationale_after_a_strength_is_stripped_the_same_way(self):
        reply = ab.parse_reply(reply_text(PREFER="A, clearly; \u2014 the summary is clearer"))
        self.assertEqual((reply.choice, reply.strength, reply.rationale),
                         ("A", "clearly", "the summary is clearer"))

    def test_a_field_runs_to_the_next_label(self):
        text = reply_text(DOUBTS="first line\nsecond line\nthird line")
        reply = ab.parse_reply(text)
        self.assertEqual(reply.fields["DOUBTS"], "first line\nsecond line\nthird line")
        self.assertEqual(reply.fields["UNDERSOLD"], "z")

    def test_a_label_inside_a_line_does_not_start_a_field(self):
        reply = ab.parse_reply(reply_text(DOUBTS="see OWNED: below\n  OWNED: indented"))
        self.assertEqual(reply.fields["DOUBTS"], "see OWNED: below\n  OWNED: indented")
        self.assertEqual(reply.fields["OWNED"], "v")

    def test_labels_are_case_sensitive_and_text_before_the_first_field_is_ignored(self):
        text = "Sure, here is my answer.\nread: lower\n" + reply_text()
        reply = ab.parse_reply(text)
        self.assertIsNone(reply.failure)
        self.assertEqual(reply.read_id, "c1/1")
        lower = ab.parse_reply(reply_text().replace("PREFER:", "prefer:"))
        self.assertEqual(lower.failure, "missing PREFER")

    def test_each_missing_required_field_fails_the_read(self):
        for label in ("READ", "SCORE-A", "SCORE-B", "PREFER"):
            with self.subTest(label):
                reply = ab.parse_reply(reply_text(**{label.replace("-", "_"): None}))
                self.assertEqual(reply.failure, "missing " + label)

    def test_10_38_the_read_value_is_not_checked(self):
        for value in ("c1/1", "anything at all", "", "7"):
            with self.subTest(value):
                reply = ab.parse_reply(reply_text(READ=value))
                self.assertIsNone(reply.failure)
                self.assertEqual((reply.choice, reply.strength), ("A", "slightly"))

    def test_10_38_a_pick_with_no_strength_is_a_failed_read(self):
        self.assertEqual(ab.parse_reply(reply_text(PREFER="A")).failure,
                         "PREFER cannot be read")

    def test_an_unreadable_prefer_fails_the_read(self):
        for value in ("C, slightly", "A", "B", "A, loudly", "A slightly", "a, slightly",
                      "A, Slightly", "tie", "Tie", "TIEBREAK", "", "A, slightlyish"):
            with self.subTest(value):
                reply = ab.parse_reply(reply_text(PREFER=value))
                self.assertEqual(reply.failure, "PREFER cannot be read")

    def test_only_the_first_line_of_prefer_counts(self):
        reply = ab.parse_reply(reply_text(PREFER="B, clearly\nA, strongly\nmore"))
        self.assertEqual((reply.choice, reply.strength), ("B", "clearly"))
        later = ab.parse_reply(reply_text(PREFER="\nA, strongly"))
        self.assertEqual(later.failure, "PREFER cannot be read")

    def test_any_integer_is_a_valid_score(self):
        for value in ("0", "11", "-3", "7", "1000"):
            with self.subTest(value):
                reply = ab.parse_reply(reply_text(SCORE_A=value, SCORE_B=value))
                self.assertIsNone(reply.failure)
                self.assertEqual((reply.score_a, reply.score_b), (int(value), int(value)))

    def test_a_missing_or_non_integer_score_is_a_failed_read(self):
        for value in ("7.5", "seven", "", "5/10", "+5", "5 points"):
            with self.subTest(value):
                self.assertEqual(ab.parse_reply(reply_text(SCORE_A=value)).failure,
                                 "SCORE-A is not an integer")
                self.assertEqual(ab.parse_reply(reply_text(SCORE_B=value)).failure,
                                 "SCORE-B is not an integer")

    def test_a_field_that_appears_twice_is_a_failed_read(self):
        for label in ab.LABELS:
            with self.subTest(label):
                reply = ab.parse_reply(reply_text() + "%s: again\n" % label)
                self.assertEqual(reply.failure, "%s appears twice" % label)

    def test_prior_is_unflagged_only_when_exactly_nothing(self):
        self.assertIsNone(ab.parse_reply(reply_text(PRIOR="nothing")).prior_flag)
        self.assertIsNone(ab.parse_reply(reply_text(PRIOR="  nothing  ")).prior_flag)
        for value in ("Nothing", "NOTHING", "nothing.", "nothing at all", "a former colleague",
                      ""):
            with self.subTest(value):
                self.assertEqual(ab.parse_reply(reply_text(PRIOR=value)).prior_flag,
                                 "PRIOR is not nothing: %s" % value)
        self.assertEqual(ab.parse_reply(reply_text(PRIOR=None)).prior_flag, "PRIOR missing")


class FakeReaderCase(unittest.TestCase):
    def read(self, arm="c1", number=1, slot_a="base", slot_b="skills-top"):
        return ab.PlannedRead(arm, number, "r1", slot_a, slot_b)

    def choice(self, rules, read=None, text_a="plain", text_b=GLANCE):
        reply = ab.parse_reply(ab.fake_reply(read or self.read(), rules, text_a, text_b))
        self.assertIsNone(reply.failure)
        return reply.choice, reply.strength

    def test_r3_seeded_random_is_pinned(self):
        # The first byte of sha256("1:aa:<k>") is a7, 05, 6e, d8, 99, 9c for k = 1 to 6.
        non_tie = [ab.random_pick(1, "aa", n, True) for n in range(1, 7)]
        self.assertEqual(non_tie, ["B", "B", "A", "A", "B", "A"])
        with_tie = [ab.random_pick(1, "aa", n) for n in range(1, 7)]
        self.assertEqual(with_tie, ["TIE", "TIE", "TIE", "A", "A", "A"])
        for flag, expected in ((True, non_tie), (False, with_tie)):
            rules = [ab.FakeRule.random(1, arms=["aa"], non_tie=flag)]
            picks = [self.choice(rules, self.read("aa", n, "skills-top", "skills-top"))[0]
                     for n in range(1, 7)]
            self.assertEqual(picks, expected)

    def test_random_depends_on_seed_arm_and_read_number_only(self):
        rules = [ab.FakeRule.random(1, arms=["aa", "c1"], non_tie=True)]
        same = [self.choice(rules, self.read("c1", n))[0] for n in range(1, 7)]
        self.assertEqual(same, [ab.random_pick(1, "c1", n, True) for n in range(1, 7)])
        self.assertNotEqual([ab.random_pick(2, "aa", n, True) for n in range(1, 13)],
                            [ab.random_pick(1, "aa", n, True) for n in range(1, 13)])
        self.assertNotEqual([ab.random_pick(1, "c1", n, True) for n in range(1, 13)],
                            [ab.random_pick(1, "aa", n, True) for n in range(1, 13)])
        # Without non-tie, all three outcomes occur.
        self.assertEqual(set(ab.random_pick(5, "c1", n) for n in range(1, 40)),
                         set(["A", "B", "TIE"]))

    def test_the_rules(self):
        glance = ab.FakeRule.prefer_containing(GLANCE)
        self.assertEqual(self.choice([glance]), ("B", "slightly"))
        self.assertEqual(self.choice([glance], text_a=GLANCE, text_b="plain"),
                         ("A", "slightly"))
        self.assertEqual(self.choice([glance], text_a=GLANCE), ("TIE", None))
        self.assertEqual(self.choice([ab.FakeRule.prefer_not_containing(GLANCE)]),
                         ("A", "slightly"))
        self.assertEqual(self.choice([ab.FakeRule.tie()]), ("TIE", None))
        self.assertEqual(self.choice([ab.FakeRule.prefer_slot("B", strength="clearly")]),
                         ("B", "clearly"))
        self.assertEqual(self.choice([]), ("TIE", None))
        self.assertEqual(self.choice([ab.FakeRule.write("DOUBTS", "x")]), ("TIE", None))

    def test_a_rule_applies_to_the_aa_arm_only_when_it_names_it(self):
        rule = ab.FakeRule.prefer_slot("A")
        aa = self.read("aa", 1, "skills-top", "skills-top")
        self.assertEqual(self.choice([rule], aa), ("TIE", None))
        self.assertEqual(self.choice([ab.FakeRule.prefer_slot("A", arms=["aa"])], aa),
                         ("A", "slightly"))
        named = ab.FakeRule.prefer_slot("A", arms=["c2"])
        self.assertEqual(self.choice([named]), ("TIE", None))
        self.assertEqual(self.choice([named], self.read("c2", 1)), ("A", "slightly"))

    def test_on_reads_gives_tie_on_every_other_read(self):
        rule = ab.FakeRule.prefer_slot("A", on_reads=[2, 4])
        self.assertEqual([self.choice([rule], self.read(number=n))[0] for n in range(1, 6)],
                         ["TIE", "A", "TIE", "A", "TIE"])

    def test_scores_are_5_and_5_unless_a_score_rule_applies(self):
        for rule in (ab.FakeRule.prefer_slot("A"), ab.FakeRule.prefer_slot("B"),
                     ab.FakeRule.tie()):
            reply = ab.parse_reply(ab.fake_reply(self.read(), [rule], "a", "b"))
            self.assertEqual((reply.score_a, reply.score_b), (5, 5))
        rules = [ab.FakeRule.prefer_slot("A"), ab.FakeRule.score(7, 4, on_reads=[2]),
                 ab.FakeRule.score(-1, 12, on_reads=[3])]
        got = [ab.parse_reply(ab.fake_reply(self.read(number=n), rules, "a", "b"))
               for n in (1, 2, 3)]
        self.assertEqual([(r.score_a, r.score_b) for r in got], [(5, 5), (7, 4), (-1, 12)])

    def test_the_last_of_several_score_rules_wins(self):
        rules = [ab.FakeRule.score(1, 2), ab.FakeRule.score(3, 4)]
        reply = ab.parse_reply(ab.fake_reply(self.read(), rules, "a", "b"))
        self.assertEqual((reply.score_a, reply.score_b), (3, 4))

    def test_write_and_omit(self):
        rules = [ab.FakeRule.write("DOUBTS", "too long"),
                 ab.FakeRule.write("DOUBTS", "and dense"),
                 ab.FakeRule.write("PREFER", "a reason"),
                 ab.FakeRule.write("PRIOR", "somebody"),
                 ab.FakeRule.omit("OWNED")]
        reply = ab.parse_reply(ab.fake_reply(self.read(), rules, "a", "b"))
        self.assertIsNone(reply.failure)
        self.assertEqual(reply.fields["DOUBTS"], "too long and dense")
        self.assertEqual(reply.rationale, "a reason")
        self.assertEqual(reply.prior_flag, "PRIOR is not nothing: somebody")
        self.assertNotIn("OWNED", reply.fields)
        self.assertEqual(reply.fields["DROVE-IT"], "none")

    def test_omit_beats_a_write_to_the_same_field(self):
        for rules in ([ab.FakeRule.write("DOUBTS", "x"), ab.FakeRule.omit("DOUBTS")],
                      [ab.FakeRule.omit("DOUBTS"), ab.FakeRule.write("DOUBTS", "x")]):
            reply = ab.parse_reply(ab.fake_reply(self.read(), rules, "a", "b"))
            self.assertNotIn("DOUBTS", reply.fields)

    def test_prior_defaults_to_nothing(self):
        reply = ab.parse_reply(ab.fake_reply(self.read(), [], "a", "b"))
        self.assertEqual(reply.fields["PRIOR"], "nothing")
        self.assertIsNone(reply.prior_flag)

    def test_a_rule_cannot_name_an_unknown_field_or_strength(self):
        with self.assertRaises(ValueError):
            ab.FakeRule.write("NOPE", "x")
        with self.assertRaises(ValueError):
            ab.FakeRule.prefer_slot("A", strength="mildly")
        with self.assertRaises(ValueError):
            ab.FakeRule.prefer_slot("C")


# ------------------------------------------------------------------ run order, slots, spend

class RunOrderCase(unittest.TestCase):
    def key_rows(self, s):
        return [line.split("\t") for line in s.read(ab.KEY_FILE).splitlines()]

    def test_10_31_odd_reads_give_first_version_the_extra_slot(self):
        s = Setup(self, readers=["r1 | fake"], reads_per_reader="5")
        self.assertEqual(s.frozen_run().exit_code, 0)
        rows = [row for row in self.key_rows(s) if row[0].startswith("c1/")]
        self.assertEqual([row[0] for row in rows], ["c1/%d" % n for n in range(1, 6)])
        self.assertEqual([row[2] for row in rows],
                         ["base", "skills-top", "base", "skills-top", "base"])
        self.assertEqual([row[3] for row in rows],
                         ["skills-top", "base", "skills-top", "base", "skills-top"])
        self.assertIn("slot split c1 r1: base in slot A 3, skills-top in slot A 2",
                      s.result_lines())

    def test_arms_run_in_order_and_readers_in_turn(self):
        s = Setup(self, comparisons=TWO)
        self.assertEqual(s.frozen_run().exit_code, 0)
        rows = self.key_rows(s)
        self.assertEqual([r[0] for r in rows],
                         ["aa/%d" % n for n in range(1, 7)] + ["c1/%d" % n for n in range(1, 7)]
                         + ["c2/%d" % n for n in range(1, 7)])
        self.assertEqual([r[1] for r in rows[:6]], ["r1", "r1", "r1", "r2", "r2", "r2"])
        for row in rows[:6]:
            self.assertEqual(row[2], row[3])
        self.assertEqual(rows[6][2:], ["base", "skills-top"])
        self.assertEqual(rows[12][2:], ["base", "skills-top-short"])

    def test_the_read_folder_holds_the_two_versions_the_posting_and_the_prompt(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        folder = s.read_folder("c1", 2)
        self.assertEqual(folder, s.path("reads", "c1", "2"))
        self.assertEqual(sorted(os.listdir(folder)),
                         ["A.txt", "B.txt", "POSTING.txt", "PROMPT.txt", "REPLY.txt"])
        for name, expected in (("A.txt", s.read("skills-top.txt")),
                               ("B.txt", s.read("base.txt")),
                               ("POSTING.txt", s.read("posting.txt")),
                               ("PROMPT.txt", ab.PROMPT)):
            with open(os.path.join(folder, name), encoding="utf-8", newline="") as handle:
                self.assertEqual(handle.read(), expected)

    def test_the_key_exists_before_the_first_read(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        seen = []
        real = ab.fake_reply

        def watching(read, rules, text_a, text_b):
            seen.append((read.id, s.exists(ab.KEY_FILE), s.reply_count(read.arm)))
            return real(read, rules, text_a, text_b)

        with mock.patch.object(ab, "fake_reply", watching):
            self.assertEqual(s.run().exit_code, 0)
        self.assertEqual(len(seen), 12)
        self.assertEqual(seen[0], ("aa/1", True, 0))
        self.assertTrue(all(key for _id, key, _replies in seen))

    def test_a_run_without_a_ceiling_spends_one_unit_per_read(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        self.assertEqual(s.read(ab.RUN_LOG).splitlines(), [
            "planned reads: 12", "reads run: 12", "spend: 12", "spend ceiling: none",
            "cut: no", "key sha256: " + sha256_of(s.path(ab.KEY_FILE))])
        self.assertIn("spend tally: 12 (a tally of declared costs, not measured spend); "
                      "ceiling: none", s.result_lines())

    def test_10_12_spend_ceiling_cuts_between_reads(self):
        s = Setup(self, comparisons=TWO, spend_ceiling="8",
                  hypotheses=["base vs skills-top | " + SIX,
                              "base vs skills-top-short | " + SHORT_SIX],
                  fake_reader=[PREFER_GLANCE])
        result = s.frozen_run()
        self.assertEqual(result.exit_code, 1)
        self.assertEqual((s.reply_count("aa"), s.reply_count("c1"), s.reply_count("c2")),
                         (6, 2, 0))
        self.assertEqual(s.read(ab.RUN_LOG).splitlines(), [
            "planned reads: 18", "reads run: 8", "spend: 8", "spend ceiling: 8", "cut: yes",
            "key sha256: " + sha256_of(s.path(ab.KEY_FILE))])
        lines = s.result_lines()
        self.assertIn("cut: ran 8 of 18 planned reads at spend ceiling 8", lines)
        self.assertIn("cut: ran 8 of 18 planned reads at spend ceiling 8",
                      result.error.splitlines())
        self.assertIn("A/A gate: passed (0 of 6 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)
        self.assertIn("hypothesis h1 counts: valid=2 base=0 skills-top=2 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h2 counts: valid=0 base=0 skills-top-short=0 tie=0", lines)
        self.assertIn("hypothesis h2 verdict: INCONCLUSIVE", lines)
        self.assertIn("read c1/3: reader=r1 A=base B=skills-top not run", lines)
        self.assertIn("failed reads: 0", lines)

    def test_a_ceiling_reached_exactly_at_the_end_is_not_a_cut(self):
        s = Setup(self, spend_ceiling="12")
        result = s.frozen_run()
        self.assertEqual(result.exit_code, 0)
        self.assertIn("cut: no", s.result_lines())

    def test_10_30_a_failed_read_with_a_cut_exits_1_and_reports_both(self):
        s = Setup(self, spend_ceiling="8", hypotheses=[SIX],
                  fake_reader=[PREFER_GLANCE, "omit PREFER | read 1"])
        result = s.frozen_run()
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read c1/1: missing PREFER",
            "cut: ran 8 of 12 planned reads at spend ceiling 8"])
        lines = s.result_lines()
        self.assertIn("failed reads: 1", lines)
        self.assertIn("failed read c1/1: missing PREFER", lines)
        self.assertIn("cut: ran 8 of 12 planned reads at spend ceiling 8", lines)
        self.assertIn("exit status: 1", lines)


# ------------------------------------------------------------------ scoring

class ScoringCase(unittest.TestCase):
    def done(self, **overrides):
        overrides.setdefault("hypotheses", [SIX])
        s = Setup(self, **overrides)
        result = s.frozen_run()
        return s, result, s.result_lines()

    def test_10_1_marker_rule_supports_skills_top(self):
        s, result, lines = self.done(fake_reader=[PREFER_GLANCE])
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("hypothesis h1 rule: " + SIX_RULE, lines)
        self.assertIn("hypothesis h1 counts: valid=6 base=0 skills-top=6 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED", lines)
        self.assertIn("A/A gate: passed (0 of 6 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)
        self.assertIn("position c1: 3 of 6 non-TIE picks in slot A (50%): no slot bias", lines)
        self.assertIn("read c1/1: reader=r1 A=base B=skills-top scores=5/5 "
                      "prefer=B, slightly flags=none", lines)
        self.assertEqual(result.text, s.read("result-1.txt"))
        self.assertIn("exit status: 0", lines)

    def test_10_2_always_tie_is_inconclusive(self):
        _s, result, lines = self.done(fake_reader=["tie"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hypothesis h1 counts: valid=6 base=0 skills-top=0 tie=6", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("position c1: 0 of 0 non-TIE picks in slot A: not assessable", lines)

    def test_10_3_slot_a_bias_is_position_inconclusive(self):
        _s, result, lines = self.done(fake_reader=["prefer slot A"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hypothesis h1 counts: valid=6 base=3 skills-top=3 tie=0", lines)
        self.assertIn("position c1: 6 of 6 non-TIE picks in slot A (100%): INCONCLUSIVE",
                      lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: position is INCONCLUSIVE on c1", lines)
        self.assertIn("A/A gate: passed (0 of 6 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)

    def test_10_8_noisy_aa_trips_the_gate(self):
        # The comparison also prefers "At a glance", so the INCONCLUSIVE comes from the gate.
        rules = [PREFER_GLANCE] + items("random seed 1 non-tie", arm="aa", strength="strongly")
        _s, result, lines = self.done(fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("A/A gate: tripped (6 of 6 valid A/A reads clearly or strongly "
                      "non-TIE, 100%; threshold 1/2)", lines)
        self.assertIn("hypothesis h1 counts: valid=6 base=0 skills-top=6 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate tripped", lines)

    def test_10_9_missing_prefer_is_a_failed_read(self):
        _s, result, lines = self.done(fake_reader=[PREFER_GLANCE, "omit PREFER | read 1"])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), ["failed read c1/1: missing PREFER"])
        self.assertIn("hypothesis h1 counts: valid=5 base=0 skills-top=5 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("read c1/1: reader=r1 A=base B=skills-top FAILED (missing PREFER)", lines)
        self.assertIn("failed reads: 1", lines)

    def test_10_9_omit_prefer_fails_the_read_whatever_else_applies(self):
        rules = [PREFER_GLANCE, "omit PREFER | read 1", 'write "x" in PREFER | read 1',
                 "score 1 2 | read 1"]
        _s, result, lines = self.done(fake_reader=rules)
        self.assertEqual(result.error.splitlines(), ["failed read c1/1: missing PREFER"])

    def test_10_10_prior_other_than_nothing_is_flagged(self):
        rules = items('write "a former colleague" in PRIOR', reads=[2])
        _s, result, lines = self.done(fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("read c1/2: reader=r1 A=skills-top B=base scores=5/5 prefer=TIE "
                      "flags=PRIOR is not nothing: a former colleague", lines)
        self.assertIn("read c1/1: reader=r1 A=base B=skills-top scores=5/5 prefer=TIE "
                      "flags=none", lines)

    def test_a_prior_written_as_capital_nothing_is_flagged(self):
        rules = items('write "Nothing" in PRIOR', reads=[2])
        _s, _result, lines = self.done(fake_reader=rules)
        self.assertIn("read c1/2: reader=r1 A=skills-top B=base scores=5/5 prefer=TIE "
                      "flags=PRIOR is not nothing: Nothing", lines)

    def test_10_11_mechanism_against_a_zero_floor(self):
        _s, result, lines = self.done(mechanisms=[TOO_LONG],
                                      fake_reader=items(WRITE_TOO_LONG, reads=[1, 2, 3, 4]))
        self.assertEqual(result.exit_code, 0)
        self.assertIn("mechanism too long in c1 count: 4 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 A/A floor: 0 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 separation: separates the versions from the "
                      "A/A floor", lines)
        self.assertIn("mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 3 or more)",
                      lines)

    def test_10_14_two_arms_and_overall_position(self):
        rules = ["base vs skills-top | prefer slot B",
                 "base vs skills-top-short | " + PREFER_GLANCE]
        _s, result, lines = self.done(
            comparisons=TWO, hypotheses=["base vs skills-top | " + SIX,
                                         "base vs skills-top-short | " + SHORT_SIX],
            fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("position c1: 0 of 6 non-TIE picks in slot A (0%): INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 counts: valid=6 base=3 skills-top=3 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("position c2: 3 of 6 non-TIE picks in slot A (50%): no slot bias", lines)
        self.assertIn("hypothesis h2 verdict: SUPPORTED", lines)
        self.assertIn("position overall: 3 of 12 non-TIE picks in slot A (25%): no slot bias",
                      lines)

    def test_10_15_mechanism_at_its_floor_cannot_separate(self):
        _s, result, lines = self.done(
            mechanisms=["jargon | default | supported at 3 or more"],
            fake_reader=['aa | write "jargon" in DOUBTS', 'write "jargon" in DOUBTS'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("mechanism jargon in c1 count: 6 of 6 valid reads", lines)
        self.assertIn("mechanism jargon in c1 A/A floor: 6 of 6 valid reads", lines)
        self.assertIn("mechanism jargon in c1 separation: unable to separate the versions",
                      lines)
        self.assertIn("mechanism jargon in c1 verdict: INCONCLUSIVE "
                      "(SUPPORTED at 3 or more)", lines)

    def test_10_16_prefer_rationale_matches_by_default_only(self):
        _s, result, lines = self.done(
            mechanisms=["NEEDS A SUMMARY | default | supported at 3 or more",
                        "needs a summary | DOUBTS | supported at 3 or more"],
            fake_reader=['write "needs a summary" in PREFER'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("mechanism NEEDS A SUMMARY in c1 count: 6 of 6 valid reads", lines)
        self.assertIn("mechanism NEEDS A SUMMARY in c1 verdict: SUPPORTED "
                      "(SUPPORTED at 3 or more)", lines)
        self.assertIn("mechanism needs a summary in c1 count: 0 of 6 valid reads", lines)
        self.assertIn("mechanism needs a summary in c1 separation: unable to separate the "
                      "versions", lines)

    def test_10_21_scoring_twice_keeps_the_first_result(self):
        s, _result, _lines = self.done(fake_reader=[PREFER_GLANCE])
        first = s.read("result-1.txt")
        self.assertEqual(s.score().exit_code, 0)
        self.assertEqual(s.score().exit_code, 0)
        self.assertEqual(s.result_names(), ["result-1.txt", "result-2.txt", "result-3.txt"])
        self.assertEqual(s.read("result-1.txt"), first)
        self.assertEqual(s.read("result-2.txt"), first)
        self.assertEqual(s.read("result-3.txt"), first)

    def test_10_22_unmarked_preference_refutes(self):
        _s, result, lines = self.done(fake_reader=[WITHOUT_GLANCE])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hypothesis h1 counts: valid=6 base=6 skills-top=0 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: REFUTED", lines)

    def test_10_23_slight_aa_picks_do_not_trip_the_gate(self):
        rules = [PREFER_GLANCE, "aa | prefer slot A | slightly"]
        _s, result, lines = self.done(fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("A/A gate: passed (0 of 6 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)
        self.assertIn("position aa: 6 of 6 non-TIE picks in slot A (100%): INCONCLUSIVE",
                      lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED", lines)

    def test_a_clearly_strong_half_of_aa_trips_the_gate_at_the_threshold(self):
        rules = items("prefer slot A", reads=[1, 3, 5], arm="aa", strength="clearly")
        _s, _result, lines = self.done(fake_reader=rules)
        self.assertIn("A/A gate: tripped (3 of 6 valid A/A reads clearly or strongly "
                      "non-TIE, 50%; threshold 1/2)", lines)
        rules = items("prefer slot A", reads=[1, 3], arm="aa", strength="clearly")
        _s, _result, lines = self.done(fake_reader=rules)
        self.assertIn("A/A gate: passed (2 of 6 valid A/A reads clearly or strongly "
                      "non-TIE; threshold 1/2)", lines)

    def test_a_failed_aa_read_means_the_gate_is_not_evaluated(self):
        rules = [PREFER_GLANCE, "aa | omit PREFER | read 1"]
        _s, result, lines = self.done(fake_reader=rules)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("A/A gate: not evaluated (5 valid reads of 6 planned)", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate was not evaluated", lines)

    def test_10_24_not_blind_reads_reported_both_ways(self):
        _s, result, lines = self.done(readers=["r1 | fake | not-blind", "r2 | fake"],
                                      fake_reader=[PREFER_GLANCE])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("reads all readers c1: valid=6 base=0 skills-top=6 tie=0", lines)
        self.assertIn("reads not-blind readers c1: valid=3 base=0 skills-top=3 tie=0", lines)
        self.assertIn("read c1/1: reader=r1 A=base B=skills-top scores=5/5 prefer=B, "
                      "slightly flags=not-blind reader", lines)
        self.assertIn("read c1/4: reader=r2 A=skills-top B=base scores=5/5 prefer=A, "
                      "slightly flags=none", lines)

    def test_10_25_scores_per_version_reader_and_aa_spread(self):
        # base is in slot A on odd reads and in slot B on even reads of the arm.
        rules = [PREFER_GLANCE]
        rules += items("score 4 8", reads=[1, 3, 5]) + items("score 8 4", reads=[2, 4, 6])
        rules += items("score 3 9", arm="aa")
        _s, _result, lines = self.done(fake_reader=rules)
        self.assertIn("scores c1 version base: scores=6 total=24 mean=4.00", lines)
        self.assertIn("scores c1 version skills-top: scores=6 total=48 mean=8.00", lines)
        self.assertIn("scores c1 reader r1 version base: scores=3 total=12 mean=4.00", lines)
        self.assertIn("scores c1 reader r2 version skills-top: scores=3 total=24 mean=8.00",
                      lines)
        self.assertIn("scores aa version skills-top: scores=12 total=72 mean=6.00", lines)
        self.assertIn("A/A score spread: 6 (highest 9, lowest 3)", lines)

    def test_10_39_scores_are_5_and_5_without_a_score_rule(self):
        _s, _result, lines = self.done(fake_reader=[PREFER_GLANCE])
        reads = [line for line in lines if line.startswith("read ")]
        self.assertEqual(len(reads), 12)
        self.assertTrue(all("scores=5/5" in line for line in reads), reads)

    def test_10_39_a_score_rule_sets_both_scores(self):
        _s, _result, lines = self.done(fake_reader=[PREFER_GLANCE, "score 7 4"])
        c1 = [line for line in lines if line.startswith("read c1/")]
        aa = [line for line in lines if line.startswith("read aa/")]
        self.assertTrue(all("scores=7/4" in line for line in c1), c1)
        self.assertTrue(all("scores=5/5" in line for line in aa), aa)
        s2, _r, _l = self.done(fake_reader=["score 7 4"])
        with open(os.path.join(s2.read_folder("c1", 1), ab.READ_REPLY),
                  encoding="utf-8") as handle:
            reply = handle.read()
        self.assertIn("SCORE-A: 7\nSCORE-B: 4\n", reply)

    def test_the_aa_spread_is_zero_on_ties(self):
        _s, _result, lines = self.done()
        self.assertIn("A/A score spread: 0 (highest 5, lowest 5)", lines)

    def test_10_26_three_missing_fields_three_named_failures(self):
        rules = [PREFER_GLANCE, "omit READ | read 1", "omit SCORE-A | read 2",
                 "omit SCORE-B | read 3"]
        _s, result, lines = self.done(fake_reader=rules)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read c1/1: missing READ", "failed read c1/2: missing SCORE-A",
            "failed read c1/3: missing SCORE-B"])
        self.assertIn("failed reads: 3", lines)
        self.assertIn("hypothesis h1 counts: valid=3 base=0 skills-top=3 tie=0", lines)

    def test_10_27_single_pick_position_not_assessable(self):
        one = "SUPPORTED if skills-top preferred in 1 or more; otherwise INCONCLUSIVE"
        _s, result, lines = self.done(hypotheses=[SIX, one],
                                      fake_reader=items(PREFER_GLANCE, reads=[2]))
        self.assertEqual(result.exit_code, 0)
        self.assertIn("position c1: 1 of 1 non-TIE picks in slot A (100%): not assessable",
                      lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h2 verdict: SUPPORTED", lines)

    def test_or_more_holds_however_many_reads_are_valid(self):
        four = "SUPPORTED if skills-top preferred in 4 or more; otherwise INCONCLUSIVE"
        _s, result, lines = self.done(hypotheses=[SIX, four],
                                      fake_reader=[PREFER_GLANCE, "omit PREFER | read 1"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h2 verdict: SUPPORTED", lines)

    def test_n_of_m_needs_exactly_m_valid_reads(self):
        # Five valid reads all prefer skills-top, but "5 of 6" needs exactly 6 valid reads.
        five_of_six = ("SUPPORTED if skills-top preferred in 5 of 6; "
                       "otherwise INCONCLUSIVE")
        _s, result, lines = self.done(hypotheses=[five_of_six],
                                      fake_reader=[PREFER_GLANCE, "omit PREFER | read 1"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("hypothesis h1 counts: valid=5 base=0 skills-top=5 tie=0", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        # The control: with all 6 reads valid the same rule is SUPPORTED.
        _s, _result, lines = self.done(hypotheses=[five_of_six], fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: SUPPORTED", lines)

    def test_the_first_clause_that_holds_decides(self):
        # Both clauses hold (all six reads prefer skills-top). The order of the plan decides.
        supported_first = ("SUPPORTED if skills-top preferred in 3 or more; "
                           "REFUTED if skills-top preferred in 2 or more; "
                           "otherwise INCONCLUSIVE")
        refuted_first = ("REFUTED if skills-top preferred in 2 or more; "
                         "SUPPORTED if skills-top preferred in 3 or more; "
                         "otherwise INCONCLUSIVE")
        _s, _result, lines = self.done(hypotheses=[supported_first, refuted_first],
                                       fake_reader=[PREFER_GLANCE])
        self.assertIn("hypothesis h1 verdict: SUPPORTED", lines)
        self.assertIn("hypothesis h2 verdict: REFUTED", lines)
        self.assertEqual([line for line in lines if "reason" in line], [])

    def test_the_result_names_the_plan_and_freeze_hashes(self):
        s, _result, lines = self.done()
        self.assertIn("plan sha256: " + sha256_of(s.path("plan.txt")), lines)
        self.assertIn("freeze sha256: " + sha256_of(s.path("plan.txt.freeze")), lines)
        self.assertIn("key c1/1: reader=r1 A=base B=skills-top", lines)
        self.assertIn("key aa/4: reader=r2 A=skills-top B=skills-top", lines)
        self.assertFalse([line for line in lines if line.startswith("amended")])

    def test_a_noise_threshold_is_a_fraction(self):
        rules = items("prefer slot A", reads=[1, 2], arm="aa", strength="strongly")
        _s, _result, lines = self.done(noise_threshold="1/3", fake_reader=rules)
        self.assertIn("A/A gate: tripped (2 of 6 valid A/A reads clearly or strongly "
                      "non-TIE, 33%; threshold 1/3)", lines)

    def test_scoring_reads_the_replies_not_the_fake_rules(self):
        s, _result, lines = self.done(fake_reader=[PREFER_GLANCE])
        reply = os.path.join(s.read_folder("c1", 1), ab.READ_REPLY)
        with open(reply, "w", encoding="utf-8") as handle:
            handle.write("READ: c1/1\nSCORE-A: 3\nSCORE-B: 9\nPREFER: A, strongly\n")
        self.assertEqual(s.score().exit_code, 0)
        later = s.result_lines(2)
        self.assertIn("read c1/1: reader=r1 A=base B=skills-top scores=3/9 prefer=A, strongly "
                      "flags=PRIOR missing", later)
        self.assertIn("hypothesis h1 counts: valid=6 base=1 skills-top=5 tie=0", later)
        self.assertNotEqual(lines, later)

    def test_10_40_unevaluated_gate_makes_mechanisms_inconclusive(self):
        rules = items(WRITE_TOO_LONG, reads=[1, 2, 3, 4]) + [PREFER_GLANCE]
        rules_failed = rules + ["aa | omit PREFER | read 1"]
        # The control: without the failed A/A read the mechanism and hypothesis stand.
        _s, ok, lines = self.done(mechanisms=[TOO_LONG], fake_reader=rules)
        self.assertEqual(ok.exit_code, 0)
        self.assertIn("mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 3 or more)",
                      lines)
        self.assertIn("hypothesis h1 verdict: SUPPORTED", lines)
        _s, result, lines = self.done(mechanisms=[TOO_LONG], fake_reader=rules_failed)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("A/A gate: not evaluated (5 valid reads of 6 planned)", lines)
        self.assertIn("mechanism too long in c1 count: 4 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 verdict: INCONCLUSIVE "
                      "(SUPPORTED at 3 or more)", lines)
        self.assertIn("mechanism too long in c1 reason: the A/A gate was not evaluated", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: the A/A gate was not evaluated", lines)

    def test_a_tripped_gate_makes_mechanisms_inconclusive_too(self):
        rules = items(WRITE_TOO_LONG, reads=[1, 2, 3, 4])
        rules += items("random seed 1 non-tie", arm="aa", strength="strongly")
        _s, result, lines = self.done(mechanisms=[TOO_LONG], fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("A/A gate: tripped (6 of 6 valid A/A reads clearly or strongly "
                      "non-TIE, 100%; threshold 1/2)", lines)
        self.assertIn("mechanism too long in c1 count: 4 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 verdict: INCONCLUSIVE "
                      "(SUPPORTED at 3 or more)", lines)
        self.assertIn("mechanism too long in c1 reason: the A/A gate tripped", lines)

    def test_10_41_position_leaves_mechanisms_alone(self):
        rules = items(WRITE_TOO_LONG, reads=[1, 2, 3, 4])
        rules.append("base vs skills-top | prefer slot B")
        _s, result, lines = self.done(mechanisms=[TOO_LONG], fake_reader=rules)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("position c1: 0 of 6 non-TIE picks in slot A (0%): INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 verdict: INCONCLUSIVE", lines)
        self.assertIn("hypothesis h1 reason: position is INCONCLUSIVE on c1", lines)
        self.assertIn("mechanism too long in c1 count: 4 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 A/A floor: 0 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 3 or more)",
                      lines)
        self.assertEqual([line for line in lines if line.startswith("mechanism")
                          and "reason" in line], [])

    def test_the_fake_reader_runs_inside_the_tool_and_starts_no_program(self):
        s = Setup(self, fake_reader=[PREFER_GLANCE])
        self.assertEqual(s.freeze().exit_code, 0)
        with mock.patch("career_track_record.ab_reader_command.run_reader_command",
                        side_effect=AssertionError("a program was started")):
            self.assertEqual(s.run().exit_code, 0)


if __name__ == "__main__":
    unittest.main()
