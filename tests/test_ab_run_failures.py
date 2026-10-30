"""Tests for the ways a Reader A/B run can fail (career_track_record.ab). All data is invented.

A folder that cannot be written or read, a key that cannot be parsed or has been changed, and
a reader that writes into its own folder each end the command with one line and no traceback;
a run that stops early still leaves a run log. The rules are in docs/specs/reader-ab.md,
Build interpretations. Where a test makes a folder read-only with ``os.chmod`` it is skipped
for a user who ignores modes (root).
"""

import hashlib
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import Setup, sha256_of  # noqa: E402
from tests.test_ab_live import reply_stub, stub_command  # noqa: E402
from tests.test_cli import track  # noqa: E402

# Known limit: a user who ignores file modes (root, or a system with no user ids) can write
# into a folder made read-only, so the tests that rely on a refused write are skipped there.
IGNORES_MODES = not hasattr(os, "geteuid") or os.geteuid() == 0
needs_modes = unittest.skipIf(IGNORES_MODES, "this user ignores file modes")


def make_read_only(case, path):
    """Make a folder read-only for the rest of the test; restore it at the end."""
    def restore():
        if os.path.exists(path):
            os.chmod(path, 0o755)
    case.addCleanup(restore)
    os.chmod(path, 0o555)


def one_line(case, err):
    """Standard error holds one line and no traceback; returns the line."""
    case.assertNotIn("Traceback", err)
    case.assertEqual(err.count("\n"), 1, err)
    return err.rstrip("\n")


class UnwritableFolderCase(unittest.TestCase):
    @needs_modes
    def test_freeze_in_a_read_only_folder_exits_2_with_one_line(self):
        s = Setup(self)
        make_read_only(self, s.folder)
        code, out, err = track("ab", "freeze", s.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err),
                         "cannot run: cannot write plan.txt.freeze: Permission denied")
        self.assertFalse(s.exists("plan.txt.freeze"))
        result = s.freeze()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error, "cannot write plan.txt.freeze: Permission denied")

    @needs_modes
    def test_run_in_a_read_only_folder_exits_2_with_one_line(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        make_read_only(self, s.folder)
        code, out, err = track("ab", "run", s.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err),
                         "cannot run: cannot write key.txt: Permission denied")
        self.assertFalse(s.exists(ab.KEY_FILE))
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertFalse(s.exists(ab.RUN_LOG))
        result = s.run()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error, "cannot write key.txt: Permission denied")

    @needs_modes
    def test_score_in_a_read_only_folder_exits_2_with_one_line(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        make_read_only(self, s.folder)
        code, out, err = track("ab", "score", s.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err),
                         "cannot run: cannot write result-2.txt: Permission denied")
        self.assertEqual(s.result_names(), ["result-1.txt"])

    @needs_modes
    def test_an_unreadable_run_log_exits_2_with_one_line(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        os.chmod(s.path(ab.RUN_LOG), 0)
        self.addCleanup(os.chmod, s.path(ab.RUN_LOG), 0o644)
        code, out, err = track("ab", "score", s.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err),
                         "cannot run: cannot read run-log.txt: Permission denied")

    @needs_modes
    def test_an_unreadable_reply_exits_2_with_one_line(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        reply = s.path(ab.READS_DIR, "c1", "2", ab.READ_REPLY)
        os.chmod(reply, 0)
        self.addCleanup(os.chmod, reply, 0o644)
        code, out, err = track("ab", "score", s.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err), "cannot run: cannot read "
                         "reads/c1/2/REPLY.txt: Permission denied")


def rewrite_key(s, change, keep_hash=False):
    """Change key.txt after a run; with ``keep_hash`` the run log is made to match."""
    s.edit(ab.KEY_FILE, change)
    if keep_hash:
        digest = sha256_of(s.path(ab.KEY_FILE))
        s.edit(ab.RUN_LOG, lambda text: "".join(
            ("key sha256: %s\n" % digest) if line.startswith("key sha256: ") else line + "\n"
            for line in text.splitlines()))


class KeyFileCase(unittest.TestCase):
    def test_a_key_line_that_cannot_be_parsed_exits_2_naming_key_txt(self):
        cases = [
            (lambda text: text.replace("aa/1\tr1\tskills-top\tskills-top",
                                       "aa/1\tr1\tskills-top", 1),
             "cannot parse key.txt: line 1 does not hold four fields separated by tabs"),
            (lambda text: text.replace("aa/1\t", "aa-one\t", 1),
             "cannot parse key.txt: line 1 does not start with a read such as c1/3"),
            (lambda text: text.replace("c1/2\t", "c1/two\t", 1),
             "cannot parse key.txt: line 8 does not start with a read such as c1/3"),
        ]
        for change, line in cases:
            with self.subTest(line):
                s = Setup(self)
                self.assertEqual(s.frozen_run().exit_code, 0)
                rewrite_key(s, change, keep_hash=True)
                result = s.score()
                self.assertEqual((result.exit_code, result.ran), (2, False))
                self.assertEqual(result.error, line)
                code, out, err = track("ab", "score", s.plan_path)
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(one_line(self, err), "cannot run: " + line)
                self.assertEqual(s.result_names(), ["result-1.txt"])

    def test_a_key_that_is_not_text_exits_2_naming_key_txt(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        with open(s.path(ab.KEY_FILE), "wb") as handle:
            handle.write(b"\xff\xfe\n")
        digest = sha256_of(s.path(ab.KEY_FILE))
        s.edit(ab.RUN_LOG, lambda text: "".join(
            ("key sha256: %s\n" % digest) if line.startswith("key sha256: ") else line + "\n"
            for line in text.splitlines()))
        result = s.score()
        self.assertEqual((result.exit_code, result.error),
                         (2, "cannot parse key.txt: not valid UTF-8"))

    def test_a_key_edited_after_the_run_exits_2_naming_key_txt(self):
        edits = {
            "emptied": lambda text: "",
            "slots swapped": lambda text: text.replace("c1/1\tr1\tbase\tskills-top",
                                                      "c1/1\tr1\tskills-top\tbase"),
            "one more line": lambda text: text + "c1/7\tr1\tbase\tskills-top\n",
        }
        for name, change in edits.items():
            with self.subTest(name):
                s = Setup(self)
                self.assertEqual(s.frozen_run().exit_code, 0)
                rewrite_key(s, change)
                result = s.score()
                self.assertEqual((result.exit_code, result.ran), (2, False))
                self.assertEqual(result.error, "changed since the run: key.txt")
                code, out, err = track("ab", "score", s.plan_path)
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(one_line(self, err),
                                 "cannot run: changed since the run: key.txt")
                self.assertEqual(s.result_names(), ["result-1.txt"])

    def test_a_run_log_with_no_key_hash_exits_2_naming_run_log_txt(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        s.edit(ab.RUN_LOG, lambda text: "".join(
            line + "\n" for line in text.splitlines() if not line.startswith("key sha256")))
        result = s.score()
        self.assertEqual((result.exit_code, result.ran), (2, False))
        self.assertEqual(result.error, "no key sha256 line in run-log.txt")
        code, out, err = track("ab", "score", s.plan_path)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err), "cannot run: no key sha256 line in run-log.txt")
        self.assertEqual(s.result_names(), ["result-1.txt"])

    def test_the_run_log_records_the_hash_of_the_key_it_wrote(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        recorded = [line for line in s.read(ab.RUN_LOG).splitlines()
                    if line.startswith("key sha256: ")]
        expected = hashlib.sha256(s.read(ab.KEY_FILE).encode("utf-8")).hexdigest()
        self.assertEqual(recorded, ["key sha256: " + expected])
        self.assertEqual(s.score().exit_code, 0)


def writes_own(*names):
    """Stub source: writes the named files into its own folder, then prints a valid reply."""
    body = "".join("open(%r, 'w').write('the reader wrote this\\n')\n" % name
                   for name in names)
    return body + reply_stub()


class ReaderWritesItsFolderCase(unittest.TestCase):
    def live(self, source, **overrides):
        reader = "r2 | " + stub_command(self, source) + " | cost 3"
        overrides.setdefault("reads_per_reader", "1")
        return Setup(self, readers=["r1 | fake", reader], **overrides)

    def check(self, source, written, name, absent):
        s = self.live(source)
        result = s.frozen_run(live=True)
        reason = "the reader wrote %s into its folder" % name
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read aa/2: " + reason, "failed read c1/2: " + reason])
        for arm in ("aa", "c1"):
            folder = s.read_folder(arm, 2)
            for file_name in written:
                with open(os.path.join(folder, file_name), "rb") as handle:
                    self.assertEqual(handle.read(), b"the reader wrote this\n")
            self.assertFalse(os.path.exists(os.path.join(folder, absent)))
        lines = s.result_lines()
        self.assertIn("read c1/2: reader=r2 A=skills-top B=base FAILED (%s)" % reason, lines)
        self.assertIn("failed reads: 2", lines)
        self.assertIn("exit status: 1", lines)
        # The declared cost counts as spent: 1 + 3 + 1 + 3.
        self.assertIn("spend: 8", s.read(ab.RUN_LOG).splitlines())
        # Scoring the folder again gives the same failed reads and leaves the files alone.
        again = s.score()
        self.assertEqual(again.exit_code, 1)
        self.assertEqual(again.text, result.text)
        return s

    def test_a_reader_that_writes_reply_txt_is_a_failed_read(self):
        self.check(writes_own(ab.READ_REPLY), [ab.READ_REPLY], ab.READ_REPLY, ab.READ_STDERR)

    def test_a_reader_that_writes_stderr_txt_is_a_failed_read(self):
        self.check(writes_own(ab.READ_STDERR), [ab.READ_STDERR], ab.READ_STDERR, ab.READ_REPLY)

    def test_a_reader_that_writes_both_is_a_failed_read_naming_reply_txt(self):
        self.check(writes_own(ab.READ_REPLY, ab.READ_STDERR),
                   [ab.READ_REPLY, ab.READ_STDERR], ab.READ_REPLY, "nothing-else.txt")

    def test_the_command_exits_1_for_a_reader_that_writes_reply_txt(self):
        s = self.live(writes_own(ab.READ_REPLY))
        self.assertEqual(track("ab", "freeze", s.plan_path)[0], 0)
        code, out, err = track("ab", "run", s.plan_path, "--live")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("read c1/2: reader=r2 A=skills-top B=base FAILED (the reader wrote "
                      "REPLY.txt into its folder)\n", out)
        self.assertNotIn("Traceback", out)


class StoppedRunCase(unittest.TestCase):
    """A run that stops early (other than at the spend ceiling) still writes its run log."""

    def stopping_setup(self):
        # Known method: the one live reader makes the A/A arm's folder read-only when it is
        # started, so the folder for read 2 of the arm cannot be made.
        source = ("import os\nos.chmod(os.path.dirname(os.getcwd()), 0o555)\n" + reply_stub())
        s = Setup(self, readers=["r1 | " + stub_command(self, source)], reads_per_reader="2")
        arm = s.path(ab.READS_DIR, "aa")

        def restore():
            if os.path.isdir(arm):
                os.chmod(arm, 0o755)
        self.addCleanup(restore)
        self.assertEqual(s.freeze().exit_code, 0)
        return s

    STOPPED = "stopped: cannot write reads/aa/2: Permission denied"
    STOPPED_ERR = "cannot run: " + STOPPED + "\n"

    @needs_modes
    def test_an_error_mid_run_leaves_a_run_log_with_a_stopped_line(self):
        s = self.stopping_setup()
        result = s.run(live=True)
        self.assertEqual((result.exit_code, result.ran), (2, True))
        self.assertTrue(s.exists(ab.KEY_FILE))
        log = s.read(ab.RUN_LOG).splitlines()
        self.assertEqual(log[:4], ["planned reads: 4", "reads run: 1", "spend: 1",
                                   "spend ceiling: none"])
        self.assertEqual(log[4], "cut: no")
        self.assertEqual(log[5], "key sha256: " + sha256_of(s.path(ab.KEY_FILE)))
        self.assertEqual(log[-1], self.STOPPED)
        lines = s.result_lines()
        self.assertIn(self.STOPPED, lines)
        self.assertIn(self.STOPPED, result.error.splitlines())
        self.assertIn("read aa/1: reader=r1 A=skills-top B=skills-top scores=6/4 "
                      "prefer=A, slightly flags=none", lines)
        self.assertIn("read aa/2: reader=r1 A=skills-top B=skills-top not run", lines)
        self.assertIn("read c1/1: reader=r1 A=base B=skills-top not run", lines)
        self.assertIn("failed reads: 0", lines)
        self.assertIn("exit status: 2", lines)

    @needs_modes
    def test_score_reports_the_stopped_line_and_exits_2(self):
        s = self.stopping_setup()
        self.assertEqual(s.run(live=True).exit_code, 2)
        result = s.score()
        self.assertEqual((result.exit_code, result.ran), (2, True))
        lines = result.text.splitlines()
        self.assertIn(self.STOPPED, lines)
        self.assertIn("read aa/2: reader=r1 A=skills-top B=skills-top not run", lines)
        self.assertEqual(s.result_names(), ["result-1.txt", "result-2.txt"])

    @needs_modes
    def test_the_command_exits_2_and_prints_the_scored_reads_and_the_stopped_line(self):
        s = self.stopping_setup()
        code, out, err = track("ab", "run", s.plan_path, "--live")
        self.assertEqual((code, err), (2, self.STOPPED_ERR))
        self.assertIn(self.STOPPED + "\n", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(s.read(ab.RUN_LOG).splitlines()[-1], self.STOPPED)
        code, out, err = track("ab", "score", s.plan_path)
        self.assertEqual((code, err), (2, self.STOPPED_ERR))
        self.assertIn(self.STOPPED + "\n", out)

    @needs_modes
    def test_a_stop_writes_one_cannot_run_line_to_standard_error(self):
        s = self.stopping_setup()
        code, out, err = track("ab", "run", s.plan_path, "--live")
        self.assertEqual(code, 2)
        self.assertEqual(err, "cannot run: stopped: cannot write reads/aa/2: "
                              "Permission denied\n")
        self.assertEqual(err.count("\n"), 1)
        self.assertNotIn("Traceback", err)
        # Standard output is the scored result, with the same reason on its own line.
        self.assertIn("\nstopped: cannot write reads/aa/2: Permission denied\n", out)
        self.assertIn("exit status: 2\n", out)
        self.assertNotIn("cannot run", out)
        # Scoring again gives the same single line.
        again_code, _out, again_err = track("ab", "score", s.plan_path)
        self.assertEqual((again_code, again_err), (2, err))
        # A run that is not stopped (a cut) writes nothing to standard error.
        cut = Setup(self, spend_ceiling="3")
        self.assertEqual(track("ab", "freeze", cut.plan_path)[0], 0)
        cut_code, _cut_out, cut_err = track("ab", "run", cut.plan_path)
        self.assertEqual((cut_code, cut_err), (1, ""))

    def test_an_error_on_the_first_read_still_leaves_a_run_log(self):
        # No mode is involved here: the call that makes a read folder is made to fail.
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        with mock.patch.object(os, "makedirs",
                               side_effect=PermissionError(13, "Permission denied")):
            result = s.run()
        self.assertEqual((result.exit_code, result.ran), (2, True))
        self.assertTrue(s.exists(ab.KEY_FILE))
        self.assertFalse(s.exists(ab.READS_DIR))
        self.assertEqual(s.read(ab.RUN_LOG).splitlines()[-1],
                         "stopped: cannot write reads/aa/1: Permission denied")
        self.assertEqual(s.read(ab.RUN_LOG).splitlines()[1], "reads run: 0")
        again = s.score()
        self.assertEqual((again.exit_code, again.ran), (2, True))
        self.assertIn("stopped: cannot write reads/aa/1: Permission denied",
                      again.text.splitlines())

    def test_an_interruption_leaves_a_run_log_with_a_stopped_line(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        real = ab.fake_reply
        calls = []

        def interrupted(read, rules, text_a, text_b):
            calls.append(read.id)
            if len(calls) == 3:
                raise KeyboardInterrupt()
            return real(read, rules, text_a, text_b)

        with mock.patch.object(ab, "fake_reply", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                s.run()
        log = s.read(ab.RUN_LOG).splitlines()
        self.assertEqual(log[1], "reads run: 2")
        self.assertEqual(log[-1], "stopped: interrupted")
        result = s.score()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("stopped: interrupted", result.text.splitlines())
        self.assertIn("read aa/3: reader=r1 A=skills-top B=skills-top not run",
                      result.text.splitlines())

    def test_a_stop_by_the_spend_ceiling_has_no_stopped_line(self):
        s = Setup(self, spend_ceiling="3")
        self.assertEqual(s.frozen_run().exit_code, 1)
        self.assertEqual([x for x in s.read(ab.RUN_LOG).splitlines()
                          if x.startswith("stopped")], [])
        self.assertEqual([x for x in s.result_lines() if x.startswith("stopped")], [])


if __name__ == "__main__":
    unittest.main()
