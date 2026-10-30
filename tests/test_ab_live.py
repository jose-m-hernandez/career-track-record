"""Tests for live readers in Reader A/B (career_track_record.ab). All data here is invented.

A "live" reader is any reader whose command is not the word ``fake``. These tests never start
a reader that reaches a network or uses credentials. Each one writes a small stub script
into its own temporary folder and names it as the command, as
``<this Python> <the stub's path>``; the only program started is this Python running that
stub. The tests that start it pass ``--live``, as the real command line requires.
"""

import os
import shlex
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import Setup, sha256_of  # noqa: E402

VALID_REPLY = ("READ: anything\nPRIOR: nothing\nSCORE-A: 6\nSCORE-B: 4\n"
               "PREFER: A, slightly\nDROVE-IT: x\nDOUBTS: y\nUNDERSOLD: z\n"
               "OVEREXPLAINED: w\nOWNED: v\nFLAG-FIXES: u\n")


def stub_command(case, source, extra=""):
    """Write ``source`` as a Python script in a fresh temporary folder and return the
    command that runs it: this Python, then the script's path, then ``extra``."""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    path = os.path.join(tmp.name, "stub.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    command = shlex.quote(sys.executable) + " " + shlex.quote(path)
    return command + (" " + extra if extra else "")


def reply_stub(**fields):
    """Source of a stub that prints a valid reply, with some fields replaced."""
    text = VALID_REPLY
    for label, value in fields.items():
        lines = [line for line in text.splitlines() if not line.startswith(label + ":")]
        text = "".join(line + "\n" for line in lines) + "%s: %s\n" % (label, value)
    return "import sys\nsys.stdout.write(%r)\n" % text


# Known limit: a reader's standard output and standard error are held in memory with no size limit; read-timeout bounds time only, so no test covers a reader that prints without end.
class LiveReaderCase(unittest.TestCase):
    def live(self, source, extra="", cost=None, **overrides):
        """A setup with a fake reader first and the stub second (one read each per arm)."""
        reader = "r2 | " + stub_command(self, source, extra)
        if cost is not None:
            reader += " | cost %d" % cost
        overrides.setdefault("reads_per_reader", "1")
        return Setup(self, readers=["r1 | fake", reader], **overrides)

    def test_10_13_live_reader_without_live_flag_only_prints(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        marker = os.path.join(tmp.name, "marker.txt")
        source = "open(%r, 'w').write('ran')\n" % marker + reply_stub()
        s = self.live(source, cost=3)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual((result.exit_code, result.ran, result.error), (0, True, ""))
        self.assertFalse(os.path.exists(marker))
        self.assertIn(shlex.quote(sys.executable), result.text)
        self.assertIn("reader r2: ", result.text)
        self.assertIn("(cost 3 per read)", result.text)
        self.assertIn("planned reads: 4\n", result.text)
        self.assertIn("estimated spend: 8 (the sum of the planned reads' declared costs; "
                      "the tool cannot see real spend)\n", result.text)
        self.assertIn("nothing was started and no reply was written", result.text)
        # Nothing was written: no key, no read folder, no run log, no result.
        self.assertEqual(sorted(os.listdir(s.folder)),
                         sorted(["plan.txt", "plan.txt.freeze", "posting.txt", "base.txt",
                                 "skills-top.txt", "skills-top-short.txt"]))
        # The same plan, run again with the flag, does start the reader.
        ran = s.run(live=True)
        self.assertEqual((ran.exit_code, ran.error), (0, ""))
        self.assertTrue(os.path.exists(marker))

    def test_a_plan_of_fake_readers_only_needs_no_live_flag(self):
        s = Setup(self)
        self.assertEqual(s.freeze().exit_code, 0)
        self.assertEqual(s.run(live=False).exit_code, 0)
        self.assertEqual(s.reply_count("c1"), 6)

    def test_the_preview_still_checks_the_freeze(self):
        s = self.live(reply_stub())
        self.assertEqual(s.freeze().exit_code, 0)
        s.edit("base.txt", lambda text: text + " \n")
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(), ["changed since the freeze: base.txt"])

    def test_10_35_stub_nonzero_exit_is_a_failed_read(self):
        source = ("import sys\n"
                  "sys.stdout.write(%r)\n"
                  "sys.stderr.write('stub failed\\n')\n"
                  "sys.exit(3)\n" % VALID_REPLY)
        s = self.live(source)
        result = s.frozen_run(live=True)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read aa/2: exit status 3", "failed read c1/2: exit status 3"])
        lines = s.result_lines()
        self.assertIn("failed reads: 2", lines)
        self.assertIn("read c1/2: reader=r2 A=skills-top B=base FAILED (exit status 3)", lines)
        # The stub's standard output is not scored: only the fake reader's read is valid.
        self.assertIn("reads all readers c1: valid=1 base=0 skills-top=0 tie=1", lines)
        self.assertFalse(s.exists(ab.READS_DIR, "c1", "2", ab.READ_REPLY))
        self.assertEqual(s.read(ab.READS_DIR, "c1", "2", ab.READ_STDERR), "stub failed\n")
        self.assertEqual(s.reply_count("c1"), 1)
        self.assertIn("exit status: 1", lines)

    # Known limit: the tool stops the reader's own process on a timeout, not processes the
    # reader started. This test uses a stub that starts none.
    def test_10_36_stub_past_timeout_is_stopped(self):
        source = "import time\ntime.sleep(5)\nprint('too late')\n"
        s = self.live(source, cost=3, read_timeout="1")
        result = s.frozen_run(live=True)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read aa/2: timed out", "failed read c1/2: timed out"])
        lines = s.result_lines()
        self.assertIn("read c1/2: reader=r2 A=skills-top B=base FAILED (timed out)", lines)
        # A timed-out read still counts its declared cost: (1 + 3) reads in each of 2 arms.
        self.assertIn("spend tally: 8 (a tally of declared costs, not measured spend); "
                      "ceiling: none", lines)
        self.assertEqual(s.read(ab.RUN_LOG).splitlines()[:5], [
            "planned reads: 4", "reads run: 4", "spend: 8", "spend ceiling: none", "cut: no"])
        self.assertFalse(s.exists(ab.READS_DIR, "c1", "2", ab.READ_REPLY))

    def test_10_37_stub_sees_exactly_four_files(self):
        source = (
            "import hashlib, os, sys\n"
            "names = sorted(os.listdir('.'))\n"
            "def digest(name):\n"
            "    with open(name, 'rb') as handle:\n"
            "        return hashlib.sha256(handle.read()).hexdigest()\n"
            "doubts = 'files=' + ','.join(names) + ' prompt=' + digest('PROMPT.txt')\n"
            "doubts += ' a=' + digest('A.txt') + ' b=' + digest('B.txt')\n"
            "doubts += ' posting=' + digest('POSTING.txt') + ' argv=' + repr(sys.argv[1:])\n"
            "sys.stdout.write('READ: anything\\nPRIOR: nothing\\nSCORE-A: 6\\n"
            "SCORE-B: 4\\nPREFER: A, slightly\\nDOUBTS: ' + doubts + '\\n')\n")
        s = self.live(source)
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run(live=True)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        reply = ab.parse_reply(s.read(ab.READS_DIR, "c1", "2", ab.READ_REPLY))
        self.assertIsNone(reply.failure)
        doubts = dict(part.split("=", 1) for part in reply.fields["DOUBTS"].split(" "))
        self.assertEqual(doubts["files"], "A.txt,B.txt,POSTING.txt,PROMPT.txt")
        frozen = [line.split("  ", 1)[0] for line in s.read("plan.txt.freeze").splitlines()
                  if line.endswith("  " + ab.PROMPT_LABEL)]
        self.assertEqual(frozen, [doubts["prompt"]])
        # Read 2 of c1 has skills-top in slot A and base in slot B.
        self.assertEqual(doubts["a"], sha256_of(s.path("skills-top.txt")))
        self.assertEqual(doubts["b"], sha256_of(s.path("base.txt")))
        self.assertEqual(doubts["posting"], sha256_of(s.path("posting.txt")))
        self.assertEqual(doubts["argv"], "[]")
        # After the read the folder also holds the reply and the log of standard error.
        self.assertEqual(sorted(os.listdir(s.read_folder("c1", 2))),
                         ["A.txt", "B.txt", "POSTING.txt", "PROMPT.txt", "REPLY.txt",
                          "STDERR.txt"])
        self.assertIn("reads all readers c1: valid=2 base=0 skills-top=1 tie=1",
                      s.result_lines())

    def test_the_command_is_split_into_words_and_run_without_a_shell(self):
        source = ("import sys\n"
                  "sys.stdout.write('READ: x\\nPRIOR: nothing\\nSCORE-A: 1\\nSCORE-B: 2\\n"
                  "PREFER: TIE\\nDOUBTS: ' + repr(sys.argv[1:]) + '\\n')\n")
        s = self.live(source, extra="--flag 'a b' \"$HOME\" '|' '*'")
        self.assertEqual(s.frozen_run(live=True).exit_code, 0)
        reply = ab.parse_reply(s.read(ab.READS_DIR, "aa", "2", ab.READ_REPLY))
        self.assertEqual(reply.fields["DOUBTS"], repr(["--flag", "a b", "$HOME", "|", "*"]))

    def test_standard_error_is_saved_and_never_scored(self):
        source = ("import sys\nsys.stdout.write(%r)\n"
                  "sys.stderr.write('PREFER: B, strongly\\nDOUBTS: from the log\\n')\n"
                  % VALID_REPLY)
        s = self.live(source, mechanisms=["from the log | default | supported at 1 or more"])
        result = s.frozen_run(live=True)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertEqual(s.read(ab.READS_DIR, "c1", "2", ab.READ_STDERR),
                         "PREFER: B, strongly\nDOUBTS: from the log\n")
        self.assertIn("mechanism from the log in c1 count: 0 of 2 valid reads",
                      s.result_lines())
        self.assertIn("read c1/2: reader=r2 A=skills-top B=base scores=6/4 prefer=A, "
                      "slightly flags=none", s.result_lines())

    def test_a_command_that_is_not_found_is_a_failed_read(self):
        s = Setup(self, readers=["r1 | fake", "r2 | /no/such/reader-program"],
                  reads_per_reader="1")
        result = s.frozen_run(live=True)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error.splitlines(), [
            "failed read aa/2: reader command not found",
            "failed read c1/2: reader command not found"])

    def test_the_spend_ceiling_is_a_tally_of_declared_costs(self):
        # Each stub read costs 3: aa/1 and aa/2 make 6, c1/1 makes 9, and the ceiling of 7 is
        # reached, so c1/2 is not started.
        s = Setup(self, readers=["r1 | " + stub_command(self, reply_stub()) + " | cost 3"],
                  reads_per_reader="2", spend_ceiling="7")
        result = s.frozen_run(live=True)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(s.read(ab.RUN_LOG).splitlines(), [
            "planned reads: 4", "reads run: 3", "spend: 9", "spend ceiling: 7", "cut: yes",
            "key sha256: " + sha256_of(s.path(ab.KEY_FILE))])
        lines = s.result_lines()
        self.assertIn("spend tally: 9 (a tally of declared costs, not measured spend); "
                      "ceiling: 7", lines)
        self.assertIn("cut: ran 3 of 4 planned reads at spend ceiling 7", lines)
        self.assertFalse(s.exists(ab.READS_DIR, "c1", "2"))

    def test_a_live_reply_is_scored_like_any_other(self):
        s = self.live(reply_stub(PREFER="B, clearly"), hypotheses=[
            "SUPPORTED if skills-top preferred in 1 or more; otherwise INCONCLUSIVE"])
        result = s.frozen_run(live=True)
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("read c1/2: reader=r2 A=skills-top B=base scores=6/4 prefer=B, clearly "
                      "flags=none", s.result_lines())
        self.assertIn("A/A gate: tripped (1 of 2 valid A/A reads clearly or strongly "
                      "non-TIE, 50%; threshold 1/2)", s.result_lines())

    def test_a_second_run_in_the_folder_of_a_live_run_is_refused(self):
        s = self.live(reply_stub())
        self.assertEqual(s.frozen_run(live=True).exit_code, 0)
        again = s.run(live=True)
        self.assertEqual(again.exit_code, 2)
        self.assertIn("the run folder already holds a run: reads", again.error.splitlines())


if __name__ == "__main__":
    unittest.main()
