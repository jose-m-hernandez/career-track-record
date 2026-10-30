"""Tests added after the second independent review of Reader A/B (career_track_record.ab).

Each test is named for one deliberate wrong change (a mutant) that the earlier suite let
through: ``test_vr2_<mutant>``. A test builds the scenario that tells the right code from the
mutant and asserts whole result lines or exact exit codes. All data here is invented. The
stubs are small Python scripts the tests write themselves; the only program started is this
Python running a stub.
"""

import io
import os
import signal
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab, cli  # noqa: E402
from tests.test_ab import EXAMPLE_PLAN, SCOPE, Setup, items  # noqa: E402
from tests.test_ab_live import VALID_REPLY, stub_command  # noqa: E402
from tests.test_cli import track  # noqa: E402

# Known limit: a user who ignores file modes (root, or a system with no user ids) can write
# into a folder made read-only, so the test that needs a refused write is skipped there.
IGNORES_MODES = not hasattr(os, "geteuid") or os.geteuid() == 0

# Known limit: a reader killed by a signal has a negative status on POSIX; the test for it is
# written for that and is skipped where a signal cannot be sent to oneself.
NO_SIGKILL = not hasattr(signal, "SIGKILL")

# Known limit: the interrupt test has a stub send SIGINT to the process that started it, so it
# is skipped where a signal cannot be sent to a parent process.
NO_SIGINT = not hasattr(signal, "SIGINT") or not hasattr(os, "getppid")


def live_setup(case, source, **overrides):
    """A fake reader first and the stub second, one read each per arm."""
    overrides.setdefault("reads_per_reader", "1")
    return Setup(case, readers=["r1 | fake", "r2 | " + stub_command(case, source)],
                 **overrides)


class LiveExitStatusCase(unittest.TestCase):
    """A live read is a success only when the reader's exit status is exactly 0."""

    def check_failed(self, source, status):
        s = live_setup(self, source)
        result = s.frozen_run(live=True)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read aa/2: exit status %d" % status,
            "failed read c1/2: exit status %d" % status])
        lines = s.result_lines()
        self.assertIn("failed reads: 2", lines)
        self.assertIn("read c1/2: reader=r2 A=skills-top B=base FAILED (exit status %d)"
                      % status, lines)
        self.assertIn("exit status: 1", lines)
        # The reply the stub printed is not scored: only the fake reader's reads are valid.
        self.assertFalse(s.exists(ab.READS_DIR, "c1", "2", ab.READ_REPLY))
        self.assertEqual(s.reply_count("c1"), 1)

    def test_vr2_r29_exit_status_1_with_a_valid_reply_is_a_failed_read(self):
        # Mutants R28 (returncode > 0) and R29 (not in (0, 1)): status 1 must fail.
        source = ("import sys\nsys.stdout.write(%r)\nsys.stdout.flush()\nsys.exit(1)\n"
                  % VALID_REPLY)
        self.check_failed(source, 1)

    @unittest.skipIf(NO_SIGKILL, "this platform has no SIGKILL")
    def test_vr2_r28_a_reader_killed_by_a_signal_is_a_failed_read(self):
        # Mutant R28 (returncode > 0): a signal gives a negative status, which must fail.
        source = ("import os, signal, sys\nsys.stdout.write(%r)\nsys.stdout.flush()\n"
                  "os.kill(os.getpid(), signal.SIGKILL)\n" % VALID_REPLY)
        self.check_failed(source, -9)


class MissingReplyCase(unittest.TestCase):
    def test_vr2_l8_a_deleted_reply_is_a_failed_read(self):
        # Mutant L8: a missing reply scored as "not run" in place of a failed read.
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        os.remove(s.path(ab.READS_DIR, "c1", "2", ab.READ_REPLY))
        result = s.score()
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), ["failed read c1/2: no reply file"])
        lines = result.text.splitlines()
        self.assertIn("failed read c1/2: no reply file", lines)
        self.assertIn("failed reads: 1", lines)
        self.assertIn("exit status: 1", lines)


class StopAndFailedReadCase(unittest.TestCase):
    @unittest.skipIf(IGNORES_MODES, "this user ignores file modes")
    def test_vr2_e7_a_stop_wins_over_a_failed_read(self):
        # Mutant E7: exit 1 when a read failed, even if the run also stopped. The one live
        # reader fails its first read (exit 3) and makes reads/aa read-only, so the folder for
        # read 2 cannot be made.
        source = ("import os, sys\nos.chmod(os.path.dirname(os.getcwd()), 0o555)\n"
                  "sys.exit(3)\n")
        s = Setup(self, readers=["r1 | " + stub_command(self, source)],
                  reads_per_reader="2")
        arm = s.path(ab.READS_DIR, "aa")

        def restore():
            if os.path.isdir(arm):
                os.chmod(arm, 0o755)
        self.addCleanup(restore)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run(live=True)
        self.assertEqual((result.exit_code, result.ran), (2, True))
        lines = s.result_lines()
        self.assertIn("failed read aa/1: exit status 3", lines)
        self.assertIn("stopped: cannot write reads/aa/2: Permission denied", lines)
        self.assertIn("exit status: 2", lines)
        self.assertEqual(s.read(ab.RUN_LOG).splitlines()[-1],
                         "stopped: cannot write reads/aa/2: Permission denied")
        again = s.score()
        self.assertEqual(again.exit_code, 2)


class MechanismSearchCase(unittest.TestCase):
    def test_vr2_x8_a_mechanism_pattern_is_searched_not_matched_at_the_start(self):
        # Mutant X8: re.match in place of re.search. The pattern is mid-text in the reply
        # field, in three comparison reads and in one A/A read.
        text = "the summary is too long here"
        rules = items('write "%s" in DOUBTS' % text, reads=[1, 2, 3])
        rules += items('write "%s" in DOUBTS' % text, reads=[1], arm="aa")
        s = Setup(self, fake_reader=rules,
                  mechanisms=["too long | default | supported at 3 or more"])
        result = s.frozen_run()
        self.assertEqual(result.exit_code, 0, result.error)
        lines = s.result_lines()
        self.assertIn("mechanism too long in c1 count: 3 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 A/A floor: 1 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 separation: separates the versions from "
                      "the A/A floor", lines)
        self.assertIn("mechanism too long in c1 verdict: SUPPORTED (SUPPORTED at 3 or more)",
                      lines)

    def test_vr2_x8_a_mid_text_floor_stops_a_mechanism_from_separating(self):
        # The A/A floor is the point: it is mid-text in every A/A read (6 of 6) and in the
        # three comparison reads (3 of 6). Only a search sees the floor, so the versions do
        # not separate from it; a match at the start sees a floor of 0 and says they do.
        text = "the summary is too long here"
        rules = items('write "%s" in DOUBTS' % text, reads=[1, 2, 3])
        rules += items('write "%s" in DOUBTS' % text, arm="aa")
        s = Setup(self, fake_reader=rules,
                  mechanisms=["too long | default | supported at 3 or more"])
        result = s.frozen_run()
        self.assertEqual(result.exit_code, 0, result.error)
        lines = s.result_lines()
        self.assertIn("mechanism too long in c1 count: 3 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 A/A floor: 6 of 6 valid reads", lines)
        self.assertIn("mechanism too long in c1 separation: unable to separate the "
                      "versions", lines)
        self.assertIn("mechanism too long in c1 verdict: INCONCLUSIVE "
                      "(SUPPORTED at 3 or more)", lines)


class EmptyScopePatternCase(unittest.TestCase):
    """A change-scope pattern that matches empty text would let every line through."""

    MESSAGE = "a change-scope pattern must not match empty text"

    def check_refused(self, pattern):
        s = Setup(self, change_scope=["^Skills$", pattern])
        result = s.freeze()
        self.assertEqual((result.exit_code, result.ran), (2, False), result.error)
        self.assertEqual(result.error.splitlines(),
                         ["plan line %d: %s" % (s.line_of(pattern), self.MESSAGE)])
        self.assertFalse(s.exists("plan.txt.freeze"))

    def test_vr2_scope_empty_branch_is_refused(self):
        self.check_refused("^Skills |")

    def test_vr2_scope_group_with_an_empty_branch_is_refused(self):
        self.check_refused("^(Skills|At a glance|)")

    def test_vr2_scope_optional_only_pattern_is_refused(self):
        self.check_refused("x?")

    def test_vr2_scope_blank_line_pattern_is_refused(self):
        # Blank lines are dropped before the isolation check, so this could never match.
        self.check_refused("^$")

    def test_vr2_scope_with_a_comparison_is_refused_too(self):
        s = Setup(self, change_scope=["base vs skills-top | x?"])
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["plan line %d: %s" % (s.line_of("x?"), self.MESSAGE)])

    def test_vr2_shipped_patterns_are_still_accepted(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            readme = handle.read().split("\n")
        start = readme.index("change-scope:") + 1
        readme_patterns = []
        for line in readme[start:]:
            if not line.startswith("  "):
                break
            readme_patterns.append(line.strip())
        example = EXAMPLE_PLAN.split("change-scope:\n")[1].split("\n")[0].strip()
        self.assertEqual(len(readme_patterns), 3)
        for patterns in (SCOPE, readme_patterns, [example], ["glance$"]):
            with self.subTest(patterns=patterns):
                s = Setup(self, change_scope=patterns)
                result = s.freeze()
                self.assertEqual((result.exit_code, result.error), (0, ""))


class StopReasonAndInterruptCase(unittest.TestCase):
    def test_vr3_the_stopped_reason_is_escaped_on_standard_error(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        with open(s.path(ab.RUN_LOG), "a", encoding="utf-8", newline="") as handle:
            handle.write("stopped: a\x1b[31mb\u2028c\\d\n")
        code, _out, err = track("ab", "score", s.plan_path)
        self.assertEqual(code, 2)
        self.assertEqual(err, "cannot run: stopped: a\\x1b[31mb\\u2028c\\\\d\n")
        self.assertEqual(len(err.splitlines()), 1)

    @unittest.skipIf(NO_SIGINT, "this platform cannot send SIGINT to a parent process")
    def test_vr3_an_interrupt_exits_2_with_one_line(self):
        source = ("import os, signal, time\n"
                  "os.kill(os.getppid(), signal.SIGINT)\n"
                  "time.sleep(5)\n")
        s = live_setup(self, source)
        self.assertEqual(s.freeze().exit_code, 0)
        code, _out, err = track("ab", "run", s.plan_path, "--live")
        self.assertEqual(code, 2, err)
        self.assertEqual(err, "cannot run: stopped: interrupted\n")
        self.assertNotIn("Traceback", err)
        self.assertEqual(s.read(ab.RUN_LOG).splitlines()[-1], "stopped: interrupted")


    # tests/test_cli.py has no in-process helper for standard error (its `track` starts a
    # process), so these two patch sys.stderr with a StringIO.
    def _interrupt_in(self, subcommand):
        s = Setup(self)
        with mock.patch("career_track_record.ab.%s" % subcommand,
                        side_effect=KeyboardInterrupt), \
                mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            code = cli.main(["ab", subcommand, s.plan_path])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue(), "cannot run: stopped: interrupted\n")
        self.assertNotIn("Traceback", err.getvalue())

    def test_vr3_an_interrupt_in_freeze_exits_2_with_one_line(self):
        self._interrupt_in("freeze")

    def test_vr3_an_interrupt_in_score_exits_2_with_one_line(self):
        self._interrupt_in("score")


if __name__ == "__main__":
    unittest.main()
