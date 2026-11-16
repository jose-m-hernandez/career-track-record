"""Tests for ``track-record barred`` comparing a text and a file name after the soft-hyphen rule.

Spec section 10.12 (revision 8): every input file that is not a PDF, and every file name, is
compared in six forms, the three of its text as read and the three of its text after a
line-end soft hyphen that follows a word character becomes a hyphen-minus. All data here is
invented. The committed fixtures used are, in tests/fixtures/barred/, the shy*.txt files and
shycomment.ts of section 10.12, soft.txt, plain.txt and clean.txt, and the lists list-l1.txt
and list-l3.txt; make_fixtures.py writes them. The file-name case and the run-time variants
are written in a temporary directory. No test reads a real list: BARRED_STRINGS_PATH and
BARRED_STRINGS are removed from every environment passed.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
sys.path.insert(0, SRC)

from career_track_record import barred  # noqa: E402

L1 = "list-l1.txt"
L3 = "list-l3.txt"
L1_PATH = os.path.join(FX, L1)
L3_PATH = os.path.join(FX, L3)
CTRL = ["--control", "Example Corp"]
PAD = "Example Corp shipped a reporting tool for teams."
SOFT_HYPHEN = chr(0xAD)
SHY_END_LINES = ["a turnkey syn" + SOFT_HYPHEN, "ergy plan"]


def clean_env(extra=None):
    env = dict(os.environ)
    env.pop("BARRED_STRINGS_PATH", None)
    env.pop("BARRED_STRINGS", None)
    env["PYTHONPATH"] = SRC
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra or {})
    return env


def run_cli(args, cwd=FX, env_extra=None):
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "career_track_record", "barred"] + list(args),
        cwd=cwd, env=clean_env(env_extra), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def padded(block, eol="\n"):
    return "".join(line + eol for line in [PAD] * 12 + list(block) + [PAD] * 12)


def write(path, text):
    with open(path, "wb") as handle:
        handle.write(text if isinstance(text, bytes) else text.encode("utf-8"))


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def fail_lines(label, findings):
    """The expected stdout of one FAIL file: findings is a list of (line, entry, count)."""
    text = "FAIL  %s: %d entries\n" % (label, len(set(f[1] for f in findings)))
    for line, entry, count in findings:
        text += "%s:%d: entry #%d (%d x)\n" % (label, line, entry, count)
    return text


def temp_run(files, extra=(), list_text=None):
    """Write each (name, bytes) into a temp directory and run the command there.

    With list_text, the list is list.txt in that directory; otherwise it is L1 by
    absolute path."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in files:
            write(os.path.join(tmp, name), content)
        if list_text is None:
            list_args = ["--list", L1_PATH]
        else:
            write(os.path.join(tmp, "list.txt"), list_text)
            list_args = ["--list", "list.txt"]
        return run_cli(list_args + CTRL + list(extra) + [name for name, _c in files],
                       cwd=tmp)


def length_of(text):
    """The length the CLI prints for a text: its first form's collapsed length (spec section 5)."""
    return len(barred._forms(text)[0][0])


def ok_line(name, entries, text):
    return "OK    %s: 0 of %d entries (control found; %d chars)\n" % (
        name, entries, length_of(text))


def fixture_text(name):
    return read(os.path.join(FX, name)).decode("utf-8")


class SoftHyphenCase(unittest.TestCase):
    def assertRun(self, args, code, out, cwd=FX):
        self.assertEqual(run_cli(args, cwd=cwd), (code, out, ""))

    def assertTempRun(self, files, code, out, **kwargs):
        self.assertEqual(temp_run(files, **kwargs), (code, out, ""))

    def fails_once(self, name, extra=()):
        self.assertRun(["--list", L1] + CTRL + list(extra) + [name], 1,
                       fail_lines(name, [(13, 1, 1)]))

    def passes(self, name, extra=()):
        self.assertRun(["--list", L1] + CTRL + list(extra) + [name], 0,
                       ok_line(name, 5, fixture_text(name)))

    def test_10_12_01_a_line_end_soft_hyphen_joins_the_word(self):
        self.fails_once("shyend.txt")

    def test_10_12_02_spaces_and_tabs_after_it_still_end_the_line(self):
        self.fails_once("shyendsp.txt")

    def test_10_12_03_crlf_line_endings(self):
        self.fails_once("shyendcrlf.txt")

    def test_10_12_04_a_lone_cr_ends_the_line(self):
        self.fails_once("shyendcr.txt")

    def test_10_12_05_a_soft_hyphen_inside_the_line_does_not_end_it(self):
        self.passes("shymid.txt")

    def test_10_12_06_a_non_word_character_before_it_stops_the_rule(self):
        self.passes("shynonword.txt")

    def test_10_12_07_a_soft_hyphen_alone_on_its_line(self):
        self.passes("shyalone.txt")

    def test_10_12_08_the_hyphen_kept_form_of_the_text_after_the_rule(self):
        self.assertTempRun([("shyend.txt", read(os.path.join(FX, "shyend.txt")))], 1,
                           fail_lines("shyend.txt", [(13, 1, 1)]),
                           list_text="turnkey syn-ergy\n")

    def test_10_12_09_nothing_matched_under_revision_7_is_lost(self):
        self.assertTempRun([("shyspace.txt", read(os.path.join(FX, "shyspace.txt")))], 1,
                           fail_lines("shyspace.txt", [(13, 1, 1)]),
                           list_text="blorf quaxel\n")
        text = fixture_text("shyspace.txt")
        self.assertIn("blorf quaxel", barred._forms(text)[0][0])
        after = barred._forms(barred._line_end_soft_hyphens(text))
        for form in after:
            self.assertNotIn("blorf quaxel", form[0])
        self.assertIn("blorf- quaxel", after[0][0])
        self.assertIn("blorfquaxel", after[1][0])
        self.assertIn("blorf-quaxel", after[2][0])

    def test_10_12_10_the_line_comes_from_the_text_as_read_first(self):
        self.assertTempRun([("shyline.txt", read(os.path.join(FX, "shyline.txt")))], 1,
                           fail_lines("shyline.txt", [(15, 1, 2)]),
                           list_text="blorfquaxel\n")

    def test_10_12_11_the_length_is_the_text_as_reads(self):
        plain = read(os.path.join(FX, "shyend.txt")).replace(SOFT_HYPHEN.encode("utf-8"), b"")
        self.assertNotEqual(plain, read(os.path.join(FX, "shyend.txt")))
        expected = ok_line("shyend.txt", 1, plain.decode("utf-8"))
        self.assertRun(["--list", L3] + CTRL + ["shyend.txt"], 0, expected)
        self.assertTempRun([("shyend.txt", plain)], 0, expected, list_text="zebra-word\n")

    def test_10_12_12_no_line_moves(self):
        content = padded(SHY_END_LINES + ["fix it"])
        self.assertTempRun([("shyend.txt", content)], 1,
                           fail_lines("shyend.txt", [(13, 1, 1), (15, 5, 1)]))

    def test_10_12_13_the_rule_applies_after_stripping_comments(self):
        self.fails_once("shycomment.ts", ["--strip-comments"])

    def test_10_12_14_without_stripping_the_comment_is_text(self):
        self.passes("shycomment.ts")

    def test_10_12_15_a_list_entry_gets_no_rule(self):
        self.assertTempRun([("plain.txt", read(os.path.join(FX, "plain.txt")))], 1,
                           fail_lines("plain.txt", [(13, 1, 1)]),
                           list_text="turnkey syn" + SOFT_HYPHEN + "\n")

    def test_10_12_16_a_control_gets_no_rule(self):
        self.assertRun(["--list", L1, "--control", "Example Corp" + SOFT_HYPHEN,
                        "clean.txt"], 0,
                       "OK    clean.txt: 0 of 5 entries (control found; 1209 chars)\n")

    def test_10_12_17_a_soft_hyphen_inside_a_line_still_matches(self):
        self.assertRun(["--list", L1] + CTRL + ["soft.txt"], 1,
                       fail_lines("soft.txt", [(13, 1, 1)]))

    def test_10_12_18_a_file_name_gets_the_rule(self):
        name = "syn" + SOFT_HYPHEN + "\nergy.txt"
        self.assertTempRun([(name, read(os.path.join(FX, "clean.txt")))], 1,
                           "FAIL  file #1: 1 entries\nfile #1:0: entry #1 (file name)\n",
                           list_text="synergy\n")

    def test_r1_the_printed_path_holds_no_soft_hyphen_or_line_break(self):
        shown = barred.printed_path("syn" + SOFT_HYPHEN + "\nergy.txt")
        self.assertNotIn(SOFT_HYPHEN, shown)
        self.assertIsNone(re.search(r"[\r\n]", shown))
        self.assertEqual(barred._line_end_soft_hyphens(shown), shown)


# The table covers text and file-name fixtures only. No PDF is in it: a PDF's text path does
# not change in revision 8, and PDF line numbers vary by poppler release.
REV7 = {
    ('list-l1.txt', False, 'bom.txt'): 'FAIL  bom.txt: 1 entries\nbom.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'case.txt'): 'FAIL  case.txt: 1 entries\ncase.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'early.txt'): 'FAIL  early.txt: 1 entries\nearly.txt:13: entry #1 (2 x)\n',
    ('list-l1.txt', False, 'emdash.txt'): 'FAIL  emdash.txt: 1 entries\nemdash.txt:13: entry #3 (1 x)\n',
    ('list-l1.txt', False, 'footnote.ts'): 'FAIL  footnote.ts: 1 entries\nfootnote.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'hyph.txt'): 'FAIL  hyph.txt: 1 entries\nhyph.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'hyphcr.txt'): 'FAIL  hyphcr.txt: 1 entries\nhyphcr.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'hyphcrlf.txt'): 'FAIL  hyphcrlf.txt: 1 entries\nhyphcrlf.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'hyphsp.txt'): 'FAIL  hyphsp.txt: 1 entries\nhyphsp.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'lig.txt'): 'FAIL  lig.txt: 1 entries\nlig.txt:13: entry #5 (1 x)\n',
    ('list-l1.txt', False, 'lines.ts'): 'FAIL  lines.ts: 1 entries\nlines.ts:15: entry #2 (1 x)\n',
    ('list-l1.txt', False, 'moonshot-notes.txt'): 'FAIL  file #1: 1 entries\nfile #1:0: entry #4 (file name)\n',
    ('list-l1.txt', False, 'moonshot-plain.txt'): 'FAIL  file #1: 1 entries\nfile #1:0: entry #4 (file name)\nfile #1:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'moonshot-short.txt'): 'DEAD  file #1: too short (40 chars, minimum 500)\n',
    ('list-l1.txt', False, 'nbsp.txt'): 'FAIL  nbsp.txt: 1 entries\nnbsp.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'nlnote.ts'): 'FAIL  nlnote.ts: 1 entries\nnlnote.ts:14: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l1.txt', False, 'plain.txt'): 'FAIL  plain.txt: 1 entries\nplain.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l1.txt', False, 'single.ts'): 'FAIL  single.ts: 1 entries\nsingle.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'soft.txt'): 'FAIL  soft.txt: 1 entries\nsoft.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'spcolon.ts'): 'FAIL  spcolon.ts: 1 entries\nspcolon.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'src.ts'): 'FAIL  src.ts: 3 entries\nsrc.ts:13: entry #1 (1 x)\nsrc.ts:14: entry #2 (1 x)\nsrc.ts:15: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'strblock.ts'): 'FAIL  strblock.ts: 1 entries\nstrblock.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'strip.txt'): 'FAIL  strip.txt: 1 entries\nstrip.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'substr.txt'): 'FAIL  substr.txt: 1 entries\nsubstr.txt:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'two.txt'): 'FAIL  two.txt: 2 entries\ntwo.txt:13: entry #1 (2 x)\ntwo.txt:13: entry #2 (1 x)\n',
    ('list-l1.txt', False, 'unterm.ts'): 'FAIL  unterm.ts: 1 entries\nunterm.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'url.ts'): 'FAIL  url.ts: 1 entries\nurl.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', False, 'value.ts'): 'FAIL  value.ts: 1 entries\nvalue.ts:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'wrap.txt'): 'FAIL  wrap.txt: 1 entries\nwrap.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', False, 'zw.txt'): 'FAIL  zw.txt: 1 entries\nzw.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'bom.txt'): 'FAIL  bom.txt: 1 entries\nbom.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'case.txt'): 'FAIL  case.txt: 1 entries\ncase.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'early.txt'): 'FAIL  early.txt: 1 entries\nearly.txt:13: entry #1 (2 x)\n',
    ('list-l1.txt', True, 'emdash.txt'): 'FAIL  emdash.txt: 1 entries\nemdash.txt:13: entry #3 (1 x)\n',
    ('list-l1.txt', True, 'footnote.ts'): 'FAIL  footnote.ts: 1 entries\nfootnote.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', True, 'hyph.txt'): 'FAIL  hyph.txt: 1 entries\nhyph.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'hyphcr.txt'): 'FAIL  hyphcr.txt: 1 entries\nhyphcr.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'hyphcrlf.txt'): 'FAIL  hyphcrlf.txt: 1 entries\nhyphcrlf.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'hyphsp.txt'): 'FAIL  hyphsp.txt: 1 entries\nhyphsp.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'lig.txt'): 'FAIL  lig.txt: 1 entries\nlig.txt:13: entry #5 (1 x)\n',
    ('list-l1.txt', True, 'lines.ts'): 'FAIL  lines.ts: 1 entries\nlines.ts:15: entry #2 (1 x)\n',
    ('list-l1.txt', True, 'moonshot-notes.txt'): 'FAIL  file #1: 1 entries\nfile #1:0: entry #4 (file name)\n',
    ('list-l1.txt', True, 'moonshot-plain.txt'): 'FAIL  file #1: 1 entries\nfile #1:0: entry #4 (file name)\nfile #1:13: entry #4 (1 x)\n',
    ('list-l1.txt', True, 'moonshot-short.txt'): 'DEAD  file #1: too short (40 chars, minimum 500)\n',
    ('list-l1.txt', True, 'nbsp.txt'): 'FAIL  nbsp.txt: 1 entries\nnbsp.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l1.txt', True, 'plain.txt'): 'FAIL  plain.txt: 1 entries\nplain.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l1.txt', True, 'single.ts'): 'FAIL  single.ts: 1 entries\nsingle.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', True, 'soft.txt'): 'FAIL  soft.txt: 1 entries\nsoft.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'spcolon.ts'): 'FAIL  spcolon.ts: 1 entries\nspcolon.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', True, 'substr.txt'): 'FAIL  substr.txt: 1 entries\nsubstr.txt:13: entry #4 (1 x)\n',
    ('list-l1.txt', True, 'two.txt'): 'FAIL  two.txt: 2 entries\ntwo.txt:13: entry #1 (2 x)\ntwo.txt:13: entry #2 (1 x)\n',
    ('list-l1.txt', True, 'unterm.ts'): 'FAIL  unterm.ts: 1 entries\nunterm.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', True, 'url.ts'): 'FAIL  url.ts: 1 entries\nurl.ts:13: entry #4 (1 x)\n',
    ('list-l1.txt', True, 'value.ts'): 'FAIL  value.ts: 1 entries\nvalue.ts:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'wrap.txt'): 'FAIL  wrap.txt: 1 entries\nwrap.txt:13: entry #1 (1 x)\n',
    ('list-l1.txt', True, 'zw.txt'): 'FAIL  zw.txt: 1 entries\nzw.txt:13: entry #1 (1 x)\n',
    ('list-l2.txt', False, 'canary.txt'): 'FAIL  canary.txt: 1 entries\ncanary.txt:13: entry #1 (1 x)\n',
    ('list-l2.txt', False, 'decomp.txt'): 'FAIL  decomp.txt: 1 entries\ndecomp.txt:13: entry #5 (1 x)\n',
    ('list-l2.txt', False, 'fold.txt'): 'FAIL  fold.txt: 1 entries\nfold.txt:13: entry #2 (1 x)\n',
    ('list-l2.txt', False, 'lrm.txt'): 'FAIL  lrm.txt: 1 entries\nlrm.txt:13: entry #2 (1 x)\n',
    ('list-l2.txt', False, 'moonshot-short.txt'): 'DEAD  moonshot-short.txt: too short (40 chars, minimum 500)\n',
    ('list-l2.txt', False, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l2.txt', False, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l2.txt', False, 'trim.txt'): 'FAIL  trim.txt: 1 entries\ntrim.txt:13: entry #3 (1 x)\n',
    ('list-l2.txt', False, 'word.txt'): 'FAIL  word.txt: 1 entries\nword.txt:13: entry #4 (2 x)\n',
    ('list-l2.txt', False, 'word2.txt'): 'FAIL  word2.txt: 1 entries\nword2.txt:13: entry #4 (1 x)\n',
    ('list-l2.txt', True, 'canary.txt'): 'FAIL  canary.txt: 1 entries\ncanary.txt:13: entry #1 (1 x)\n',
    ('list-l2.txt', True, 'decomp.txt'): 'FAIL  decomp.txt: 1 entries\ndecomp.txt:13: entry #5 (1 x)\n',
    ('list-l2.txt', True, 'fold.txt'): 'FAIL  fold.txt: 1 entries\nfold.txt:13: entry #2 (1 x)\n',
    ('list-l2.txt', True, 'lrm.txt'): 'FAIL  lrm.txt: 1 entries\nlrm.txt:13: entry #2 (1 x)\n',
    ('list-l2.txt', True, 'moonshot-short.txt'): 'DEAD  moonshot-short.txt: too short (40 chars, minimum 500)\n',
    ('list-l2.txt', True, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l2.txt', True, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l2.txt', True, 'trim.txt'): 'FAIL  trim.txt: 1 entries\ntrim.txt:13: entry #3 (1 x)\n',
    ('list-l2.txt', True, 'word.txt'): 'FAIL  word.txt: 1 entries\nword.txt:13: entry #4 (2 x)\n',
    ('list-l2.txt', True, 'word2.txt'): 'FAIL  word2.txt: 1 entries\nword2.txt:13: entry #4 (1 x)\n',
    ('list-l3.txt', False, 'hyphff1.txt'): 'FAIL  hyphff1.txt: 1 entries\nhyphff1.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', False, 'hyphff2.txt'): 'FAIL  hyphff2.txt: 1 entries\nhyphff2.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', False, 'hyphkeep.txt'): 'FAIL  hyphkeep.txt: 1 entries\nhyphkeep.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', False, 'hyphkeepcrlf.txt'): 'FAIL  hyphkeepcrlf.txt: 1 entries\nhyphkeepcrlf.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', False, 'moonshot-short.txt'): 'DEAD  moonshot-short.txt: too short (40 chars, minimum 500)\n',
    ('list-l3.txt', False, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l3.txt', False, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l3.txt', True, 'hyphff1.txt'): 'FAIL  hyphff1.txt: 1 entries\nhyphff1.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', True, 'hyphff2.txt'): 'FAIL  hyphff2.txt: 1 entries\nhyphff2.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', True, 'hyphkeep.txt'): 'FAIL  hyphkeep.txt: 1 entries\nhyphkeep.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', True, 'hyphkeepcrlf.txt'): 'FAIL  hyphkeepcrlf.txt: 1 entries\nhyphkeepcrlf.txt:13: entry #1 (1 x)\n',
    ('list-l3.txt', True, 'moonshot-short.txt'): 'DEAD  moonshot-short.txt: too short (40 chars, minimum 500)\n',
    ('list-l3.txt', True, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l3.txt', True, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l4.txt', False, 'hyphff1.txt'): 'FAIL  hyphff1.txt: 2 entries\nhyphff1.txt:13: entry #1 (1 x)\nhyphff1.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', False, 'hyphff2.txt'): 'FAIL  hyphff2.txt: 2 entries\nhyphff2.txt:13: entry #1 (1 x)\nhyphff2.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', False, 'hyphkeep.txt'): 'FAIL  hyphkeep.txt: 2 entries\nhyphkeep.txt:13: entry #1 (1 x)\nhyphkeep.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', False, 'hyphkeepcrlf.txt'): 'FAIL  hyphkeepcrlf.txt: 2 entries\nhyphkeepcrlf.txt:13: entry #1 (1 x)\nhyphkeepcrlf.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', False, 'moonshot-short.txt'): 'DEAD  moonshot-short.txt: too short (40 chars, minimum 500)\n',
    ('list-l4.txt', False, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l4.txt', False, 'nokeep.txt'): 'FAIL  nokeep.txt: 2 entries\nnokeep.txt:13: entry #1 (1 x)\nnokeep.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', False, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l4.txt', False, 'word.txt'): 'FAIL  file #1: 1 entries\nfile #1:0: entry #2 (file name)\n',
    ('list-l4.txt', True, 'hyphff1.txt'): 'FAIL  hyphff1.txt: 2 entries\nhyphff1.txt:13: entry #1 (1 x)\nhyphff1.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', True, 'hyphff2.txt'): 'FAIL  hyphff2.txt: 2 entries\nhyphff2.txt:13: entry #1 (1 x)\nhyphff2.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', True, 'hyphkeep.txt'): 'FAIL  hyphkeep.txt: 2 entries\nhyphkeep.txt:13: entry #1 (1 x)\nhyphkeep.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', True, 'hyphkeepcrlf.txt'): 'FAIL  hyphkeepcrlf.txt: 2 entries\nhyphkeepcrlf.txt:13: entry #1 (1 x)\nhyphkeepcrlf.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', True, 'moonshot-short.txt'): 'DEAD  moonshot-short.txt: too short (40 chars, minimum 500)\n',
    ('list-l4.txt', True, 'nocontrol.txt'): 'DEAD  nocontrol.txt: control not found\n',
    ('list-l4.txt', True, 'nokeep.txt'): 'FAIL  nokeep.txt: 2 entries\nnokeep.txt:13: entry #1 (1 x)\nnokeep.txt:14: entry #2 (1 x)\n',
    ('list-l4.txt', True, 'short.txt'): 'DEAD  short.txt: too short (40 chars, minimum 500)\n',
    ('list-l4.txt', True, 'word.txt'): 'FAIL  file #1: 1 entries\nfile #1:0: entry #2 (file name)\n',
}

FINDING = re.compile(r"\A(?P<label>.+):(?P<line>[0-9]+): entry #(?P<entry>[0-9]+) "
                     r"\((?P<count>[0-9]+) x\)\Z")
NAME_FINDING = re.compile(r"\A.+:0: entry #[0-9]+ \(file name\)\Z")


def expected_exit(stdout):
    return {"FAIL": 1, "DEAD": 2}[stdout.split(" ", 1)[0]]


def findings(stdout):
    """(label, line, entry, count) for every line-numbered finding of a FAIL output."""
    found = []
    for text in stdout.splitlines()[1:]:
        match = FINDING.match(text)
        if match and not NAME_FINDING.match(text):
            found.append((match["label"], int(match["line"]), int(match["entry"]),
                          int(match["count"])))
    return found


class FailOpenRegressionCase(unittest.TestCase):
    def test_the_table_holds_every_revision_7_exit_1_and_exit_2_run(self):
        codes = [expected_exit(out) for out in REV7.values()]
        self.assertEqual(len(REV7), 112)
        self.assertEqual(codes.count(1), 88)
        self.assertEqual(codes.count(2), 24)
        self.assertEqual(list(REV7), sorted(REV7))

    def test_rev7_matches_are_kept(self):
        for (listing, strip, name), old in REV7.items():
            with self.subTest(list=listing, strip=strip, fixture=name):
                extra = ["--strip-comments"] if strip else []
                code, out, err = run_cli(["--list", listing] + CTRL + extra + [name])
                self.assertEqual(err, "")
                self.assertEqual(code, expected_exit(old))
                if code == 2:
                    self.assertEqual(out, old)
                    continue
                new_lines = out.splitlines()
                for text in old.splitlines():
                    if NAME_FINDING.match(text):
                        self.assertIn(text, new_lines)
                new = findings(out)
                for label, line, entry, count in findings(old):
                    self.assertTrue(
                        any(n[0] == label and n[1] == line and n[2] == entry and n[3] >= count
                            for n in new),
                        (label, line, entry, count, out))


if __name__ == "__main__":
    unittest.main()
