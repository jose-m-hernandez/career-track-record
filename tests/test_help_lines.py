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
_TOP_HEAD = "usage: track-record [-h] [--version] command ...\n\npositional arguments:\n  command\n"
_TOP_ROWS = (
    ("keywords", "scan saved job postings for terms"),
    ("barred", "report wording from your own barred list"),
    ("tone", "flag hype, hedges and filler in your copy"),
    ("ab", "compare two versions of your copy with test readers"),
    ("claims", "fail on sentences your claims list hasn't approved"),
    ("panel", "read one version blind through named lenses"),
    ("record", "check your record's tables against rules you declare"),
)
_DRAFTS = ("drafts", "check a file of a document's versions, or extract one")
_ABSENCE = "show that your listed terms appear nowhere in the files you declare"
# argparse wraps the description of absence onto a second line on both interpreters.
_ABSENCE_LINES = ("show that your listed terms appear nowhere in the files", "you declare")
_WRAPPED = "find hyphenated words split across two lines in a PDF"
_PARSE = "check what a text extractor gets from your résumé PDF"


def _top_help(column, wrap, options):
    rows = "".join(("    " + name).ljust(column) + text + "\n" for name, text in _TOP_ROWS)
    rows += ("    absence").ljust(column) + _ABSENCE_LINES[0] + "\n"
    rows += " " * column + _ABSENCE_LINES[1] + "\n"
    rows += ("    " + _DRAFTS[0]).ljust(column) + _DRAFTS[1] + "\n"
    if wrap:
        rows += "    wrapped-compounds\n" + " " * column + _WRAPPED + "\n"
    else:
        rows += ("    wrapped-compounds").ljust(column) + _WRAPPED + "\n"
    rows += "    parse".ljust(column) + _PARSE + "\n"
    rows += "    setup".ljust(column) + "choose your record folder\n"
    return (_TOP_HEAD + rows + "\n" + options + ":\n" + "  -h, --help".ljust(column) +
            "show this help message and exit\n" + "  --version".ljust(column) +
            "show program's version number and exit\n")


# argparse's own layout, captured once on each interpreter the base help was captured on:
# 3.9 puts the descriptions in column 21 and wraps the long name onto its own line; 3.14
# puts them in column 23 and keeps it on one line.
TOP_HELP = {
    "3.9": _top_help(21, True, "optional arguments"),
    "3.14": _top_help(23, False, "options"),
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

    def test_s39_the_top_level_help_adds_setup_parse_and_wrapped_compounds_and_nothing_else(self):
        """Three lines are added to the eight of the base: setup, then (above it) parse, then
        (above that) wrapped-compounds. The name wrapped-compounds is longer than any other,
        so argparse widens the description column of every line and, on 3.9, wraps its own
        line: the spaces change, the words do not. The exact text is pinned per interpreter in TOP_HELP, and the
        words alone (spaces collapsed) must be the base's words with the three new entries."""
        text = help_of("")
        before = self.base["(top)"]
        eight = [line for line in before.splitlines() if line.startswith("    ")]
        self.assertEqual(len(eight), 8)
        added = ("    wrapped-compounds  find hyphenated words split across two lines in a PDF\n"
                 "    parse     " + _PARSE + "\n"
                 "    setup     choose your record folder\n")
        # absence stands between record and drafts, the seventh and eighth lines of the base.
        absence = "    absence   " + _ABSENCE + "\n"
        expected_words = before.replace(eight[-2] + "\n", eight[-2] + "\n" + absence)
        expected_words = expected_words.replace(eight[-1] + "\n", eight[-1] + "\n" + added)
        # The top-level --version flag adds one usage word and one option line.
        expected_words = (expected_words.replace("[-h] command", "[-h] [--version] command")
                          + "  --version  show program's version number and exit\n")
        self.assertEqual(text.split(), expected_words.split())
        self.assertEqual(text, TOP_HELP["%d.%d" % sys.version_info[:2]])

    def test_the_top_level_help_names_wrapped_compounds_once_before_setup(self):
        words = help_of("").split()
        self.assertEqual(words.count("wrapped-compounds"), 1)
        self.assertLess(words.index("drafts"), words.index("wrapped-compounds"))
        self.assertLess(words.index("wrapped-compounds"), words.index("setup"))

    def test_the_top_level_help_names_parse_once_between_wrapped_compounds_and_setup(self):
        words = help_of("").split()
        self.assertEqual(words.count("parse"), 1)
        self.assertLess(words.index("wrapped-compounds"), words.index("parse"))
        self.assertLess(words.index("parse"), words.index("setup"))

    def test_the_top_level_help_names_absence_once_between_record_and_drafts(self):
        words = help_of("").split()
        self.assertEqual(words.count("absence"), 1)
        self.assertLess(words.index("record"), words.index("absence"))
        self.assertLess(words.index("absence"), words.index("drafts"))

    def test_the_new_lines_are_the_ones_the_code_pins(self):
        from career_track_record import cli
        self.assertEqual(NEW["barred"] in cli._BARRED_HELP, True)
        self.assertEqual(NEW["tone"] in cli._TONE_HELP, True)
        self.assertEqual(NEW["claims"] in cli._CLAIMS_HELP, True)


if __name__ == "__main__":
    unittest.main()
