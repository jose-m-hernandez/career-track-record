"""Help text: only three lines change, and every other command's help is as it was.

The expected texts of the other commands are the help the code printed before the config
existed (tests/fixtures/resolution/base-help.json, captured once from that code on each
interpreter, because argparse words its own help differently from Python 3.10). All data here
is invented."""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BASE_HELP = os.path.join(ROOT, "tests", "fixtures", "resolution", "base-help.json")
sys.path.insert(0, SRC)

OLD = {
    "barred": "  --list FILE       the list file (default: $BARRED_STRINGS_PATH)\n",
    "tone": "  --rules FILE      the rule file (default: the shipped rules)\n",
    "claims": "  --list FILE      the claims list (required)\n",
}
NEW = {
    "barred": "  --list FILE       the list file (default: $BARRED_STRINGS_PATH, else your "
              "record folder)\n",
    "tone": "  --rules FILE      the rule file (default: your record folder, else the shipped "
            "rules)\n",
    "claims": "  --list FILE      the claims list (required unless claims-list.txt is in your "
              "record folder)\n",
}
UNCHANGED = ("keywords", "keywords demand", "keywords coverage", "keywords report", "record",
             "drafts", "ab", "ab freeze", "ab run", "ab score", "panel", "panel freeze",
             "panel run", "panel score")


def help_of(command):
    env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-m", "career_track_record"] + command.split()
                          + ["-h"], env=env, stdin=subprocess.DEVNULL, capture_output=True,
                          cwd=ROOT)
    assert proc.returncode == 0 and proc.stderr == b"", command
    return proc.stdout.decode("utf-8")


def base():
    with open(BASE_HELP, encoding="utf-8") as handle:
        every = json.load(handle)
    return every["%d.%d" % sys.version_info[:2]]


class HelpLines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.base = base()
        except KeyError:
            raise unittest.SkipTest("no captured help for this interpreter")

    def test_s39_every_other_command_s_help_is_byte_identical_to_the_base(self):
        for command in UNCHANGED:
            with self.subTest(command=command):
                self.assertEqual(help_of(command), self.base[command])

    def test_s39_the_three_new_lines_are_there_and_the_three_old_are_gone(self):
        for command in ("barred", "tone", "claims"):
            with self.subTest(command=command):
                text = help_of(command)
                self.assertEqual(text.count(NEW[command]), 1)
                self.assertNotIn(OLD[command], text)
                self.assertIn(OLD[command], self.base[command])

    def test_s39_the_three_commands_change_only_that_one_line(self):
        for command in ("barred", "tone", "claims"):
            with self.subTest(command=command):
                self.assertEqual(help_of(command),
                                 self.base[command].replace(OLD[command], NEW[command]))

    def test_s39_the_top_level_help_adds_setup_as_a_ninth_line_and_changes_nothing_else(self):
        text = help_of("")
        before = self.base["(top)"]
        eight = [line for line in before.splitlines() if line.startswith("    ")]
        self.assertEqual(len(eight), 8)
        expected = before.replace(eight[-1] + "\n",
                                  eight[-1] + "\n    setup     choose your record folder\n")
        self.assertEqual(text, expected)

    def test_the_new_lines_are_the_ones_the_code_pins(self):
        from career_track_record import cli
        self.assertEqual(NEW["barred"] in cli._BARRED_HELP, True)
        self.assertEqual(NEW["tone"] in cli._TONE_HELP, True)
        self.assertEqual(NEW["claims"] in cli._CLAIMS_HELP, True)


if __name__ == "__main__":
    unittest.main()
