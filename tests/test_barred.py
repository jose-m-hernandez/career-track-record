"""Tests for ``track-record barred``: every case of docs/specs/barred.md section 10.

All data here is invented. The fixtures come from tests/fixtures/barred/make_fixtures.py.
No test reads a real list: every run removes BARRED_STRINGS_PATH and BARRED_STRINGS from
the environment it passes, and adds BARRED_STRINGS_PATH back only to name a fixture list.
"""

import ast
import io
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
FX = os.path.join(ROOT, "tests", "fixtures", "barred")
sys.path.insert(0, SRC)

from career_track_record import barred, cli  # noqa: E402

L1 = "list-l1.txt"
L2 = "list-l2.txt"
CTRL = ["--control", "Example Corp"]
PAD = "Example Corp shipped a reporting tool for teams."
PAD_LINE = PAD + "\n"
OK_CLEAN = "OK    clean.txt: 0 of 5 entries (control found; 1209 chars)\n"

L1_ENTRIES = ["turnkey synergy", "rockstar ninja", "—", "moonshot", "fix it"]
L2_ENTRIES = ["barred-strings-canary-example0001", "grossweg", "padded phrase", "fix",
              "café"]
L2_WORD = [False, False, False, True, False]


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
        [sys.executable, "-m", "career_track_record", "barred"] + list(args),
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


# Spec section 10.2's badutf8.txt: the byte 0xFF inside "synergy". It is written at run time,
# never committed, because the repository's history scan refuses a file that is not UTF-8.
BADUTF8 = padded(["turnkey syn\x00ergy"]).encode("utf-8").replace(b"syn\x00ergy", b"syn\xffergy")
OK_BADUTF8 = "OK    badutf8.txt: 0 of 5 entries (control found; 1193 chars)\n"


def fail_lines(label, findings):
    """The expected stdout of one FAIL file: findings is a list of (line, entry, count)."""
    text = "FAIL  %s: %d entries\n" % (label, len(set(f[1] for f in findings)))
    for line, entry, count in findings:
        text += "%s:%d: entry #%d (%d x)\n" % (label, line, entry, count)
    return text


class RunCase(unittest.TestCase):
    def assertRun(self, args, code, out, cwd=FX, env_extra=None):
        got_code, got_out, got_err = run_cli(args, cwd=cwd, env_extra=env_extra)
        self.assertEqual((got_code, got_out, got_err), (code, out, ""))

    def assertCannot(self, args, message, cwd=FX, env_extra=None, absent=()):
        code, out, err = run_cli(args, cwd=cwd, env_extra=env_extra)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(err, "cannot run: %s\n" % message)
        self.assertEqual(len(err.splitlines()), 1)
        for text in absent:
            self.assertNotIn(text, err)

    def one(self, name, listing, findings, extra=()):
        self.assertRun(["--list", listing] + CTRL + list(extra) + [name], 1,
                       fail_lines(name, findings))


class EvasionCase(RunCase):
    def test_each_evasion_still_matches(self):
        for name in ("plain.txt", "case.txt", "wrap.txt", "hyph.txt", "hyphcrlf.txt",
                     "hyphcr.txt", "hyphsp.txt", "soft.txt", "zw.txt", "nbsp.txt"):
            with self.subTest(name):
                self.one(name, L1, [(13, 1, 1)])

    def test_ligature_matches_entry_5(self):
        self.one("lig.txt", L1, [(13, 5, 1)])

    def test_em_dash_matches_entry_3(self):
        self.one("emdash.txt", L1, [(13, 3, 1)])


class PassCase(RunCase):
    def test_files_that_must_pass(self):
        for name in ("clean.txt", "endash.txt", "compound.txt", "note.txt",
                     "nbhyph.txt"):
            with self.subTest(name):
                code, out, err = run_cli(["--list", L1] + CTRL + [name])
                self.assertEqual((code, err), (0, ""))
                self.assertRegex(out, r"\AOK    %s: 0 of 5 entries \(control found; "
                                      r"[0-9]+ chars\)\n\Z" % re.escape(name))

    def test_badutf8_must_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "badutf8.txt"), BADUTF8)
            self.assertRun(["--list", os.path.join(FX, L1)] + CTRL + ["badutf8.txt"], 0,
                           OK_BADUTF8, cwd=tmp)

    def test_clean_prints_its_length(self):
        self.assertRun(["--list", L1] + CTRL + ["clean.txt"], 0, OK_CLEAN)


class CountCase(RunCase):
    def test_two_entries_in_order(self):
        self.assertRun(["--list", L1] + CTRL + ["two.txt"], 1,
                       "FAIL  two.txt: 2 entries\n"
                       "two.txt:13: entry #1 (2 x)\n"
                       "two.txt:13: entry #2 (1 x)\n")

    def test_substring(self):
        self.one("substr.txt", L1, [(13, 4, 1)])

    def test_earliest_line_across_both_forms(self):
        self.one("early.txt", L1, [(13, 1, 2)])

    def test_byte_order_mark_does_not_move_a_line(self):
        self.one("bom.txt", L1, [(13, 1, 1)])


class SourceCase(RunCase):
    # Known limit: an unterminated "/*" repeated many times is slow (block-comment matching is quadratic); the result is still correct.
    def test_without_strip_comments(self):
        self.one("src.ts", L1, [(13, 1, 1), (14, 2, 1), (15, 4, 1)])

    def test_with_strip_comments(self):
        code, out, err = run_cli(["--list", L1] + CTRL + ["--strip-comments", "src.ts"])
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"\AOK    src.ts: 0 of 5 entries \(control found; [0-9]+ chars\)\n\Z")

    def test_block_that_spans_lines_keeps_line_numbers(self):
        self.one("lines.ts", L1, [(15, 2, 1)], extra=["--strip-comments"])

    def test_the_other_source_fixtures(self):
        for name in ("url.ts", "footnote.ts", "spcolon.ts", "single.ts", "unterm.ts"):
            with self.subTest(name):
                self.one(name, L1, [(13, 4, 1)], extra=["--strip-comments"])

    def test_note_value_after_a_line_break_is_removed(self):
        for name in ("nlnote.ts", "strblock.ts", "strip.txt"):
            with self.subTest(name):
                code, out, err = run_cli(["--list", L1] + CTRL + ["--strip-comments", name])
                self.assertEqual((code, err), (0, ""))
                self.assertRegex(out, r"\AOK    %s: 0 of 5 entries \(control found; "
                                      r"[0-9]+ chars\)\n\Z" % re.escape(name))

    def test_other_fields_are_still_checked(self):
        self.one("value.ts", L1, [(13, 1, 1)], extra=["--strip-comments"])


class DeadAndCannotRunCase(RunCase):
    def test_short_file_is_dead(self):
        self.assertRun(["--list", L1] + CTRL + ["short.txt"], 2,
                       "DEAD  short.txt: too short (40 chars, minimum 500)\n")

    def test_no_control_found_is_dead_never_fail(self):
        self.assertRun(["--list", L1] + CTRL + ["nocontrol.txt"], 2,
                       "DEAD  nocontrol.txt: control not found\n")

    def test_min_chars_zero_still_needs_the_control(self):
        self.assertRun(["--list", L1] + CTRL + ["--min-chars", "0", "short.txt"], 2,
                       "DEAD  short.txt: control not found\n")
        self.assertRun(["--list", L1] + CTRL + ["--min-chars", "40", "short.txt"], 2,
                       "DEAD  short.txt: control not found\n")

    def test_the_499_500_edge_and_the_final_line_feed(self):
        def text(length, final_lf):
            body = "Example Corp" + "a" * (length - 12 - (1 if final_lf else 0))
            return body + ("\n" if final_lf else "")

        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "n499.txt"), text(499, False))
            write(os.path.join(tmp, "n500.txt"), text(500, False))
            write(os.path.join(tmp, "n500lf.txt"), text(500, True))
            write(os.path.join(tmp, "n499lf.txt"), text(499, True))
            base = ["--list", os.path.join(FX, L1)] + CTRL
            self.assertRun(base + ["n499.txt"], 2,
                           "DEAD  n499.txt: too short (499 chars, minimum 500)\n", cwd=tmp)
            self.assertRun(base + ["n499lf.txt"], 2,
                           "DEAD  n499lf.txt: too short (499 chars, minimum 500)\n", cwd=tmp)
            self.assertRun(base + ["n500.txt"], 0,
                           "OK    n500.txt: 0 of 5 entries (control found; 500 chars)\n",
                           cwd=tmp)
            self.assertRun(base + ["n500lf.txt"], 0,
                           "OK    n500lf.txt: 0 of 5 entries (control found; 500 chars)\n",
                           cwd=tmp)
            # An LF-terminated file counts one more than the same text without it.
            self.assertRun(base + ["--min-chars", "499", "n499.txt", "n499lf.txt"], 0,
                           "OK    n499.txt: 0 of 5 entries (control found; 499 chars)\n"
                           "OK    n499lf.txt: 0 of 5 entries (control found; 499 chars)\n",
                           cwd=tmp)
            clean = read(os.path.join(FX, "clean.txt"))
            self.assertTrue(clean.endswith(b"\n"))
            write(os.path.join(tmp, "nolf.txt"), clean[:-1])
            self.assertRun(base + ["nolf.txt"], 0,
                           "OK    nolf.txt: 0 of 5 entries (control found; 1208 chars)\n",
                           cwd=tmp)

    def test_ok_fail_dead_in_one_run(self):
        self.assertRun(["--list", L1] + CTRL + ["clean.txt", "plain.txt", "short.txt"], 2,
                       OK_CLEAN
                       + "FAIL  plain.txt: 1 entries\nplain.txt:13: entry #1 (1 x)\n"
                       + "DEAD  short.txt: too short (40 chars, minimum 500)\n")

    def test_missing_input_is_dead_and_the_rest_run(self):
        self.assertRun(["--list", L1] + CTRL + ["clean.txt", "absent.txt", "plain.txt"], 2,
                       OK_CLEAN + "DEAD  absent.txt: cannot read\n"
                       + "FAIL  plain.txt: 1 entries\nplain.txt:13: entry #1 (1 x)\n")

    def test_control_is_folded(self):
        self.assertRun(["--list", L1, "--control", "EXAMPLE CORP", "clean.txt"], 0, OK_CLEAN)

    def test_any_one_control_passes(self):
        self.assertRun(["--list", L1, "--control", "no such text", "--control", "Example Corp",
                        "clean.txt"], 0, OK_CLEAN)

    def test_a_control_that_folds_to_nothing_proves_nothing(self):
        self.assertCannot(["--list", L1, "--control", "​", "clean.txt"],
                          "no usable --control given")

    def test_no_input_file(self):
        self.assertCannot(["--list", L1] + CTRL, "no input file")

    def test_no_control(self):
        self.assertCannot(["--list", L1, "clean.txt"], "no --control given")

    def test_missing_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            gone = os.path.join(tmp, "gone.txt")
            self.assertCannot(["--list", gone] + CTRL + ["clean.txt"],
                              "the list file cannot be read", absent=[gone, "gone"])

    def test_unreadable_list_shares_the_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertCannot(["--list", tmp] + CTRL + ["clean.txt"],
                              "the list file cannot be read", absent=[tmp])

    def test_list_that_is_not_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.txt")
            write(path, b"caf\xe9\n")
            self.assertCannot(["--list", path] + CTRL + ["clean.txt"],
                              "the list is not valid UTF-8", absent=[path])

    def assertListCannot(self, content, message):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "case-list.txt")
            write(path, content)
            self.assertCannot(["--list", path] + CTRL + ["clean.txt"], message,
                              absent=[path, "case-list"])

    def test_list_with_only_comments_and_blanks(self):
        self.assertListCannot("# only a comment\n\n   \n  # an indented comment\n\t\n",
                              "the list has no entries")
        self.assertListCannot("", "the list has no entries")

    def test_empty_entries(self):
        self.assertListCannot("   \tnote\n", "entry 1 is empty")
        self.assertListCannot("​\n", "entry 1 is empty")
        self.assertListCannot("moonshot\n  ​ \n", "entry 2 is empty")
        self.assertListCannot("# c\nmoonshot\n\nfix it\n​‍\n", "entry 3 is empty")

    def test_canary_cannot_carry_the_word_flag(self):
        with open(os.path.join(FX, L2), encoding="utf-8") as handle:
            text = handle.read()
        marked = text.replace("barred-strings-canary-example0001\n",
                              "barred-strings-canary-example0001\tword\n")
        self.assertNotEqual(marked, text)
        self.assertListCannot(marked, "entry 1 is a canary and cannot carry the word flag")

    def test_a_later_canary_lookalike_may_carry_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.txt")
            write(path, "moonshot\nbarred-strings-canary-example0001\tWord\n")
            code, out, err = run_cli(["--list", path] + CTRL + ["clean.txt"])
            self.assertEqual((code, err), (0, ""))

    def test_short_canary_lookalike_is_an_ordinary_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.txt")
            write(path, "barred-strings-canary-short\tword\n")
            code, out, err = run_cli(["--list", path] + CTRL + ["clean.txt"])
            self.assertEqual((code, err), (0, ""))

    def test_form_feed_unicode_separators_and_lone_cr(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = ["--list", os.path.join(FX, L1)] + CTRL
            write(os.path.join(tmp, "ff.txt"), padded(["page\fturnkey synergy"]))
            write(os.path.join(tmp, "ls.txt"), padded(["x turnkey synergy y"]))
            write(os.path.join(tmp, "cr.txt"), padded(["turnkey synergy"], eol="\r"))
            for name in ("ff.txt", "ls.txt", "cr.txt"):
                with self.subTest(name):
                    self.assertRun(base + [name], 1, fail_lines(name, [(13, 1, 1)]), cwd=tmp)

    def test_form_feed_after_a_hyphen_is_not_a_line_break(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "f.txt"), padded(["turnkey syn-\fergy"]))
            code, out, err = run_cli(["--list", os.path.join(FX, L1)] + CTRL + ["f.txt"],
                                     cwd=tmp)
            self.assertEqual((code, err), (0, ""))
            self.assertRegex(out, r"\AOK    f.txt: 0 of 5 entries \(control found; [0-9]+ chars\)\n\Z")


class ListSourceCase(RunCase):
    def test_environment_variable_names_the_list(self):
        path = os.path.join(FX, L1)
        names = ["clean.txt", "two.txt", "short.txt"]
        by_option = run_cli(["--list", L1] + CTRL + names)
        by_env = run_cli(CTRL + names, env_extra={"BARRED_STRINGS_PATH": path})
        self.assertEqual(by_env, by_option)
        self.assertEqual(by_env[0], 2)
        self.assertNotIn(path, by_env[1] + by_env[2])

    def test_variable_unset(self):
        self.assertCannot(CTRL + ["clean.txt"],
                          "no list (give --list or set BARRED_STRINGS_PATH)")

    def test_variable_set_but_empty(self):
        self.assertCannot(CTRL + ["clean.txt"],
                          "no list (give --list or set BARRED_STRINGS_PATH)",
                          env_extra={"BARRED_STRINGS_PATH": ""})

    def test_option_wins_over_the_variable(self):
        self.assertRun(["--list", L1] + CTRL + ["clean.txt"], 0, OK_CLEAN,
                       env_extra={"BARRED_STRINGS_PATH": os.path.join(FX, "no-such-list")})

    def test_variable_pointing_nowhere_cannot_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            gone = os.path.join(tmp, "gone.txt")
            self.assertCannot(CTRL + ["clean.txt"], "the list file cannot be read",
                              env_extra={"BARRED_STRINGS_PATH": gone}, absent=[gone])

    def test_main_takes_an_explicit_environment(self):
        path = os.path.join(FX, L1)
        target = os.path.join(FX, "clean.txt")
        old = (sys.stdout, sys.stderr)
        try:
            sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
            code = cli.main(["barred", "--control", "Example Corp", target],
                            environ={"BARRED_STRINGS_PATH": path})
            out, err = sys.stdout.getvalue(), sys.stderr.getvalue()
            sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
            code_none = cli.main(["barred", "--control", "Example Corp", target], environ={})
            out_none, err_none = sys.stdout.getvalue(), sys.stderr.getvalue()
        finally:
            sys.stdout, sys.stderr = old
        self.assertEqual((code, err), (0, ""))
        self.assertIn("0 of 5 entries (control found; 1209 chars)", out)
        self.assertEqual((code_none, out_none), (2, ""))
        self.assertEqual(err_none,
                         "cannot run: no list (give --list or set BARRED_STRINGS_PATH)\n")


class OptionErrorCase(RunCase):
    def assertOptionError(self, args, message):
        # A missing input file is named: if it were opened, a DEAD line would show.
        code, out, err = run_cli(["never-created.txt"] + args)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(err, "cannot run: %s\n" % message)
        self.assertNotIn("DEAD", out + err)
        self.assertNotIn("never-created", out + err)
        self.assertNotIn(L1, err)

    def test_list_twice(self):
        self.assertOptionError(["--list", L1, "--list", L1] + CTRL, "--list given twice")

    def test_min_chars_twice(self):
        self.assertOptionError(["--list", L1] + CTRL + ["--min-chars", "1", "--min-chars", "2"],
                               "--min-chars given twice")

    def test_min_chars_out_of_range(self):
        for value in ("-1", "x", "", "1.5", "٣"):
            with self.subTest(value):
                self.assertOptionError(["--list", L1] + CTRL + ["--min-chars", value],
                                       "--min-chars must be a whole number, 0 or more")

    # Known limit: "--list --bogus" takes "--bogus" as the list path; it fails closed (the list cannot be read).
    def test_unknown_option(self):
        self.assertOptionError(["--list", L1] + CTRL + ["--frobnicate"],
                               "unknown option")

    def test_missing_values(self):
        self.assertOptionError(["--list", L1, "--control"], "--control needs a value")
        self.assertOptionError(CTRL + ["--list"], "--list needs a value")
        self.assertOptionError(["--list", L1] + CTRL + ["--min-chars"],
                               "--min-chars needs a value")
        self.assertOptionError(["--list", "--strip-comments"] + CTRL,
                               "--list needs a value")

    def test_flag_with_a_value(self):
        self.assertOptionError(["--list", L1] + CTRL + ["--strip-comments=yes"],
                               "--strip-comments takes no value")

    def test_abbreviations_are_not_accepted(self):
        self.assertOptionError(["--list", L1] + CTRL + ["--strip"], "unknown option")

    def test_the_list_value_is_never_echoed(self):
        code, out, err = run_cli(["--list", "secret-list-name", "--list", "x"] + CTRL
                                 + ["clean.txt"])
        self.assertEqual((code, out, err), (2, "", "cannot run: --list given twice\n"))
        code, out, err = run_cli(["--list=secret-list-name", "--bogus=secret-list-name"]
                                 + CTRL + ["clean.txt"])
        self.assertEqual((code, out), (2, ""))
        self.assertNotIn("secret", err)
        self.assertEqual(len(err.splitlines()), 1)

    def test_an_unknown_option_is_never_echoed(self):
        code, out, err = run_cli(["--list", L1, "--control", "Example Corp", "--moonshot",
                                  "clean.txt"])
        self.assertEqual((code, out, err), (2, "", "cannot run: unknown option\n"))
        for entry in L1_ENTRIES:
            self.assertNotIn(entry, err)

    def test_equals_form_works(self):
        self.assertRun(["--list=" + L1, "--control=Example Corp", "--min-chars=0", "clean.txt"],
                       0, OK_CLEAN)

    def test_double_dash_ends_the_options(self):
        self.assertRun(["--list", L1] + CTRL + ["--", "clean.txt"], 0, OK_CLEAN)


class ListFormatCase(RunCase):
    def test_each_list_rule(self):
        cases = [("fold.txt", 2, 1), ("trim.txt", 3, 1), ("word.txt", 4, 2),
                 ("word2.txt", 4, 1), ("decomp.txt", 5, 1), ("lrm.txt", 2, 1),
                 ("canary.txt", 1, 1)]
        for name, entry, count in cases:
            with self.subTest(name):
                self.one(name, L2, [(13, entry, count)])

    def test_clean_against_l2(self):
        self.assertRun(["--list", L2] + CTRL + ["clean.txt"], 0, OK_CLEAN)

    def test_prefix_notes_passes_because_fix_is_a_word_entry(self):
        self.assertRun(["--list", L2] + CTRL + ["prefix-notes.txt"], 0,
                       "OK    prefix-notes.txt: 0 of 5 entries (control found; 1209 chars)\n")

    def test_l1_variant_gives_the_same_results(self):
        with open(os.path.join(FX, L1), encoding="utf-8", newline="") as handle:
            text = handle.read()
        self.assertIn("# an invented list\n", text)
        variant = "﻿" + text.replace("# an invented list", "  # an invented list")
        variant = variant.replace("\n", "\r\n")
        names = ["plain.txt", "clean.txt"]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "variant.txt")
            write(path, variant)
            got = run_cli(["--list", path] + CTRL + names)
        want = run_cli(["--list", L1] + CTRL + names)
        self.assertEqual(got, want)
        self.assertIn("FAIL  plain.txt: 1 entries\nplain.txt:13: entry #1 (1 x)\n", got[1])
        self.assertEqual(want[0], 1)
        self.assertIn("OK    clean.txt: 0 of 5 entries", want[1])

    def test_lone_cr_list_and_u2028_inside_an_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.txt")
            write(path, "turnkey synergy\rrockstar ninja\r")
            code, out, err = run_cli(["--list", path] + CTRL + ["two.txt"])
            self.assertEqual((code, err), (1, ""))
            self.assertEqual(out, "FAIL  two.txt: 2 entries\ntwo.txt:13: entry #1 (2 x)\n"
                                  "two.txt:13: entry #2 (1 x)\n")
            # U+2028 is not a line break, so this is still one entry; it is whitespace,
            # so the entry prepares to the phrase "turnkey synergy" and matches plain.txt.
            write(path, "turnkey synergy\n")
            code, out, err = run_cli(["--list", path] + CTRL + ["plain.txt"])
            self.assertEqual((code, err), (1, ""))
            self.assertEqual(out, "FAIL  plain.txt: 1 entries\nplain.txt:13: entry #1 (1 x)\n")

    def test_load_list_numbers_and_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.txt")
            write(path, "﻿# c\n\nAlpha\tWoRd\tnote\r\n  # d\n Beta \tnote: word\n")
            entries = barred.load_list(path)
        self.assertEqual([(e.number, e.folded, e.word) for e in entries],
                         [(1, "alpha", True), (2, "beta", False)])

    def test_load_list_errors_are_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.txt")
            with self.assertRaises(barred.ListError) as caught:
                barred.load_list(path)
            self.assertNotIn(path, str(caught.exception))


class PreparedCase(RunCase):
    """Spec revision 3: entries, controls and file names have whitespace runs collapsed."""

    def run_list(self, text, args):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.txt")
            write(path, text)
            return run_cli(["--list", path] + args)

    def test_entry_with_a_double_space_matches(self):
        for name in ("plain.txt", "wrap.txt"):
            with self.subTest(name):
                code, out, err = self.run_list("turnkey  synergy\n", CTRL + [name])
                self.assertEqual((code, err), (1, ""))
                self.assertEqual(out, "FAIL  %s: 1 entries\n%s:13: entry #1 (1 x)\n"
                                 % (name, name))

    def test_control_with_a_double_space_passes(self):
        self.assertRun(["--list", L1, "--control", "Example  Corp", "clean.txt"], 0, OK_CLEAN)

    def test_a_blank_control_alone_cannot_run(self):
        self.assertCannot(["--list", L1, "--control", "   ", "clean.txt"],
                          "no usable --control given")

    def test_a_blank_control_beside_a_usable_one(self):
        self.assertRun(["--list", L1, "--control", "   ", "--control", "Example Corp",
                        "clean.txt"], 0, OK_CLEAN)

    def test_an_entry_of_format_characters_and_a_space_is_empty(self):
        code, out, err = self.run_list("​ ​\n", CTRL + ["clean.txt"])
        self.assertEqual((code, out, err), (2, "", "cannot run: entry 1 is empty\n"))

    def test_preparing_trims_what_folding_leaves(self):
        code, out, err = self.run_list("​turnkey synergy\n", CTRL + ["plain.txt"])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, "FAIL  plain.txt: 1 entries\nplain.txt:13: entry #1 (1 x)\n")

    def test_file_name_is_prepared(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = "moon  shot notes.txt"
            write(os.path.join(tmp, name), read(os.path.join(FX, "clean.txt")))
            write(os.path.join(tmp, "l.txt"), "moon shot\n")
            code, out, err = run_cli(["--list", "l.txt"] + CTRL + [name], cwd=tmp)
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, "FAIL  file #1: 1 entries\nfile #1:0: entry #1 (file name)\n")


class FileNameCase(RunCase):
    def test_name_alone(self):
        self.assertRun(["--list", L1] + CTRL + ["moonshot-notes.txt"], 1,
                       "FAIL  file #1: 1 entries\nfile #1:0: entry #4 (file name)\n")

    def test_name_in_second_position(self):
        self.assertRun(["--list", L1] + CTRL + ["clean.txt", "moonshot-notes.txt"], 1,
                       OK_CLEAN + "FAIL  file #2: 1 entries\nfile #2:0: entry #4 (file name)\n")

    def test_name_and_text(self):
        self.assertRun(["--list", L1] + CTRL + ["moonshot-plain.txt"], 1,
                       "FAIL  file #1: 1 entries\nfile #1:0: entry #4 (file name)\n"
                       "file #1:13: entry #4 (1 x)\n")

    def test_dead_file_with_a_matching_name_has_no_finding_lines(self):
        self.assertRun(["--list", L1] + CTRL + ["moonshot-short.txt"], 2,
                       "DEAD  file #1: too short (40 chars, minimum 500)\n")

    def test_missing_file_with_a_matching_name_keeps_the_label_rule(self):
        self.assertRun(["--list", L1] + CTRL + ["moonshot-absent.txt"], 2,
                       "DEAD  file #1: cannot read\n")


def contains_entry(text, entry, word):
    """Independent search: the literal entry, and for a word entry the boundary rule."""
    start = 0
    while True:
        at = text.find(entry, start)
        if at < 0:
            return False
        if not word:
            return True
        end = at + len(entry)

        def edge(ch):
            category = unicodedata.category(ch)
            return not (category.startswith("L") or category == "Nd")

        if (at == 0 or edge(text[at - 1])) and (end == len(text) or edge(text[end])):
            return True
        start = at + 1


SWEEP = [
    (L1, ["plain.txt", "case.txt", "wrap.txt", "hyph.txt", "hyphcrlf.txt", "hyphcr.txt",
          "hyphsp.txt", "soft.txt", "zw.txt", "nbsp.txt", "lig.txt", "emdash.txt"], []),
    (L1, ["clean.txt", "endash.txt", "compound.txt", "note.txt", "nbhyph.txt"], []),
    (L1, ["two.txt", "substr.txt", "early.txt", "bom.txt"], []),
    (L1, ["src.ts", "value.ts"], []),
    (L1, ["src.ts", "lines.ts", "nlnote.ts", "url.ts", "footnote.ts", "spcolon.ts",
          "single.ts", "unterm.ts", "strblock.ts", "strip.txt", "value.ts"],
     ["--strip-comments"]),
    (L1, ["short.txt", "nocontrol.txt", "clean.txt", "plain.txt", "absent.txt"], []),
    (L1, ["moonshot-notes.txt", "clean.txt", "moonshot-plain.txt", "moonshot-short.txt"], []),
    (L2, ["fold.txt", "trim.txt", "word.txt", "word2.txt", "decomp.txt", "lrm.txt",
          "canary.txt", "clean.txt", "prefix-notes.txt", "moonshot-notes.txt"], []),
]


class NothingBarredIsPrintedCase(RunCase):
    def fixture_names(self):
        return sorted(n for n in os.listdir(FX)
                      if n != "make_fixtures.py" and not n.startswith("__"))

    def test_the_search_finds_each_entry_in_the_list_files(self):
        for listing, entries in ((L1, L1_ENTRIES), (L2, L2_ENTRIES)):
            with open(os.path.join(FX, listing), encoding="utf-8") as handle:
                text = handle.read()
            for entry in entries:
                self.assertIn(entry, text)

    def test_no_run_prints_an_entry_a_name_that_matches_or_a_list_path(self):
        by_list = {L1: [(e, False) for e in L1_ENTRIES],
                   L2: list(zip(L2_ENTRIES, L2_WORD))}
        runs = 0
        for listing, names, extra in SWEEP:
            checks = by_list[listing]
            matching_names = set()
            for name in self.fixture_names():
                for entry, word in checks:
                    if contains_entry(name.lower(), entry, word):
                        matching_names.add(name)
            if listing == L1:
                self.assertIn("moonshot-notes.txt", matching_names)
            else:
                # Named like the word entry `fix`, but not as a whole word: not a match.
                self.assertNotIn("prefix-notes.txt", matching_names)
            captured = run_cli(["--list", listing] + CTRL + extra + names)
            captured_text = captured[1] + captured[2]
            runs += 1
            for entry, word in checks:
                self.assertFalse(contains_entry(captured_text.lower(), entry, word),
                                 (listing, names))
            for name in matching_names:
                self.assertNotIn(name, captured_text)
            self.assertNotIn(L1, captured_text)
            self.assertNotIn(L2, captured_text)
            self.assertNotIn(FX, captured_text)
        self.assertEqual(runs, len(SWEEP))

    def test_the_badutf8_run_prints_no_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "badutf8.txt"), BADUTF8)
            code, out, err = run_cli(["--list", os.path.join(FX, L1)] + CTRL + ["badutf8.txt"],
                                     cwd=tmp)
        self.assertEqual((code, out, err), (0, OK_BADUTF8, ""))
        for entry in L1_ENTRIES:
            self.assertFalse(contains_entry((out + err).lower(), entry, False), entry)
        self.assertNotIn(L1, out + err)
        self.assertNotIn(FX, out + err)

    def test_cannot_run_messages_print_no_entry_and_no_list_path(self):
        path = os.path.join(FX, L1)
        for args in (["--list", L1] + CTRL, ["--list", L1, "clean.txt"],
                     ["--list", L1, "--list", L1] + CTRL + ["clean.txt"]):
            code, out, err = run_cli(args)
            for entry in L1_ENTRIES:
                self.assertNotIn(entry, out + err)
            self.assertNotIn(L1, out + err)
        code, out, err = run_cli(CTRL + ["clean.txt"], env_extra={"BARRED_STRINGS_PATH": path})
        self.assertNotIn(path, out + err)


class NeverWritesCase(RunCase):
    def snapshot(self, paths):
        return dict((p, (read(p), os.stat(p).st_mtime_ns)) for p in paths)

    def test_inputs_and_lists_are_unchanged(self):
        names = [n for n in os.listdir(FX)
                 if n != "make_fixtures.py" and not n.startswith("__")]
        paths = [os.path.join(FX, n) for n in names]
        before = self.snapshot(paths)
        listing = sorted(os.listdir(FX))
        run_cli(["--list", L1] + CTRL + ["--strip-comments"] + sorted(names))
        run_cli(["--list", L2] + CTRL + sorted(names))
        self.assertEqual(sorted(os.listdir(FX)), listing)
        self.assertEqual(self.snapshot(paths), before)


class ListIsNotALabelCase(RunCase):
    """Spec sections 6 and 8: the list's path is never printed, even as an input."""

    WANT = "DEAD  file #1: control not found\n"

    def check(self, args, env_extra=None):
        code, out, err = run_cli(args, env_extra=env_extra)
        self.assertEqual((code, out, err), (2, self.WANT, ""))
        self.assertNotIn(L1, out + err)

    def test_list_given_as_an_input(self):
        self.check(["--list", L1] + CTRL + ["--min-chars", "0", L1])

    def test_a_different_spelling_of_the_path(self):
        self.check(["--list", L1] + CTRL + ["--min-chars", "0", "./" + L1])
        self.check(["--list", "./" + L1] + CTRL + ["--min-chars", "0", L1])

    def test_list_named_by_the_variable(self):
        self.check(CTRL + ["--min-chars", "0", L1],
                   env_extra={"BARRED_STRINGS_PATH": os.path.join(FX, L1)})
        self.check(CTRL + ["--min-chars", "0", "./" + L1],
                   env_extra={"BARRED_STRINGS_PATH": os.path.join(FX, L1)})


class NonUtf8ArgumentCase(RunCase):
    def test_a_path_that_is_not_utf8_does_not_crash(self):
        code, out, err = run_cli(["--list", L1] + CTRL + [b"bad\xffname.txt"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "DEAD  bad\\udcffname.txt: cannot read\n")
        self.assertNotIn("Traceback", err)


class GapCase(unittest.TestCase):
    """Rules the tool already follows, each pinned by one exact run in a temp directory."""

    def run_in(self, list_text, name, content, extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "list.txt"), list_text)
            write(os.path.join(tmp, name), content)
            return run_cli(["--list", "list.txt"] + CTRL + list(extra) + [name], cwd=tmp)

    def expect(self, list_text, name, content, code, out, extra=()):
        self.assertEqual(self.run_in(list_text, name, content, extra), (code, out, ""))

    def fail_text(self, name, entry):
        return "FAIL  %s: 1 entries\n%s:13: entry #%d (1 x)\n" % (name, name, entry)

    def test_helpers_do_not_shadow_testcase_fail(self):
        self.assertIs(GapCase.fail, unittest.TestCase.fail)

    def ok(self, name, entries, chars):
        return ("OK    %s: 0 of %d entries (control found; %d chars)\n"
                % (name, entries, chars))

    def test_01_overlapping_matches_do_not_count_twice(self):
        self.expect("aa\n", "overlap.txt", padded(["xx aaa xx"]), 1,
                    self.fail_text("overlap.txt", 1))

    def test_02_word_scan_resumes_one_character_on(self):
        self.expect("ab ab\tword\n", "wordskip.txt", padded(["zab ab ab"]), 1,
                    self.fail_text("wordskip.txt", 1))

    def test_03_a_note_that_is_not_the_flag_is_not_word(self):
        self.expect("fix\twordy\n", "wordnote.txt", padded(["a prefix here"]), 1,
                    self.fail_text("wordnote.txt", 1))

    def test_04_form_feed_is_not_a_line_break_for_rejoining(self):
        self.expect("turnkey synergy\n", "ffbreak.txt",
                    padded(["a turnkey syn-\f", "ergy plan"]), 0,
                    self.ok("ffbreak.txt", 1, 1201))

    def test_05_rejoin_needs_a_word_character_before(self):
        self.expect("turnkey ergy\n", "nobefore.txt", padded(["a turnkey -", "ergy plan"]),
                    0, self.ok("nobefore.txt", 1, 1198))

    def test_06_rejoin_needs_a_word_character_after(self):
        self.expect("syn(ergy\n", "noafter.txt", padded(["a turnkey syn-", "(ergy plan"]),
                    0, self.ok("noafter.txt", 1, 1202))

    def test_07_underscore_is_a_word_character_for_rejoining_only(self):
        self.expect("a_x\n", "under.txt", padded(["a_-", "x b"]), 1,
                    self.fail_text("under.txt", 1))

    def l1_copy(self):
        return read(os.path.join(FX, L1))

    def test_08_a_comment_on_the_first_line_is_stripped(self):
        content = "// turnkey synergy\n" + PAD_LINE * 24
        self.expect(self.l1_copy(), "nlstart.txt", content, 0,
                    self.ok("nlstart.txt", 5, 1177), extra=["--strip-comments"])

    def test_09_string_concatenation_is_not_a_note_value(self):
        self.expect(self.l1_copy(), "plus.ts", padded(['x = { note: "a" + "moonshot" };']),
                    0, self.ok("plus.ts", 5, 1191), extra=["--strip-comments"])

    def test_10_two_block_comments_leave_the_text_between(self):
        self.expect(self.l1_copy(), "twoblocks.ts", padded(["/* a */ moonshot /* b */"]),
                    1, self.fail_text("twoblocks.ts", 4), extra=["--strip-comments"])

    def test_11_the_control_is_matched_in_the_joined_form_only(self):
        content = "Lorem ipsum dolor sit amet, invented filler text for length.\n" * 12
        content += "Exam-\nple Corp\n"
        self.expect(self.l1_copy(), "ctlsplit.txt", content, 2,
                    "DEAD  ctlsplit.txt: control not found\n")

    def test_12_a_number_that_is_not_nd_is_a_boundary(self):
        self.expect("fix\tword\n", "nonnd.txt", padded(["we fix\u09f4 now"]), 1,
                    self.fail_text("nonnd.txt", 1))

    def test_13_folding_ends_in_nfkc(self):
        self.expect("j\n", "caron.txt", padded(["the \u01f0 sign"]), 0,
                    self.ok("caron.txt", 1, 1187))


FILLER_LINE = "Lorem ipsum dolor sit amet, invented filler text for length.\n"


class RuleGapCase(RunCase):
    """Rules the tool already follows (second set), each pinned by one exact run."""

    def make(self, tmp, list_text, files):
        write(os.path.join(tmp, "list.txt"), list_text)
        for name, content in files.items():
            write(os.path.join(tmp, name), content)

    def expect(self, list_text, name, content, code, out, extra=(), ctrl=None):
        ctrl = CTRL if ctrl is None else ctrl
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, list_text, {name: content})
            got = run_cli(["--list", "list.txt"] + ctrl + list(extra) + [name], cwd=tmp)
        self.assertEqual(got, (code, out, ""))

    def fail_text(self, name, entry, line=13):
        return "FAIL  %s: 1 entries\n%s:%d: entry #%d (1 x)\n" % (name, name, line, entry)

    def ok(self, name, entries, chars):
        return ("OK    %s: 0 of %d entries (control found; %d chars)\n"
                % (name, entries, chars))

    def l1(self):
        return read(os.path.join(FX, L1))

    def clean(self):
        return read(os.path.join(FX, "clean.txt"))

    def test_01_a_blank_control_beside_a_real_one_never_passes_a_file(self):
        self.expect(self.l1(), "noctl.txt", FILLER_LINE * 12, 2,
                    "DEAD  noctl.txt: control not found\n",
                    ctrl=["--control", "   ", "--control", "absent phrase"])

    def test_02_word_flag_matches_at_the_start_of_the_text(self):
        self.expect("fix\tword\n", "wstart.txt", "fix it now\n" + PAD_LINE * 24, 1,
                    self.fail_text("wstart.txt", 1, 1))

    def test_03_word_flag_matches_at_the_end_without_a_final_newline(self):
        self.expect("fix\tword\n", "wend.txt", PAD_LINE * 24 + "we fix", 1,
                    self.fail_text("wend.txt", 1, 25))

    def test_04_a_note_with_a_trailing_space_is_not_the_flag(self):
        self.expect("fix\tword \n", "wflagsp.txt", padded(["a prefix here"]), 1,
                    self.fail_text("wflagsp.txt", 1))

    def test_05_a_tab_after_the_hyphen_is_still_a_rejoin(self):
        self.expect("turnkey synergy\n", "tab.txt",
                    padded(["a turnkey syn-\t", "ergy plan"]), 1,
                    self.fail_text("tab.txt", 1))

    def test_06_an_indent_after_the_break_is_still_a_rejoin(self):
        self.expect("turnkey synergy\n", "indent.txt",
                    padded(["a turnkey syn-", "    ergy plan"]), 1,
                    self.fail_text("indent.txt", 1))

    def test_07_a_digit_is_a_word_character_for_rejoining(self):
        self.expect("abc12\n", "digit.txt", padded(["x abc-", "12 y"]), 1,
                    self.fail_text("digit.txt", 1))

    def test_08_the_length_is_the_joined_forms(self):
        self.expect(self.l1(), "lenrj.txt", padded(["we co-", "operate"]), 0,
                    self.ok("lenrj.txt", 5, 1191))

    def test_09_every_cf_character_is_removed(self):
        self.expect("turnkey synergy\n", "cf2064.txt",
                    padded(["turn⁤key synergy"]), 1, self.fail_text("cf2064.txt", 1))

    def test_10_a_near_canary_may_carry_the_word_flag(self):
        self.expect("barred-strings-canary-example0001!\tword\n", "clean.txt",
                    self.clean(), 0, self.ok("clean.txt", 1, 1209))

    def test_11_a_seven_character_tail_is_not_a_canary(self):
        self.expect("barred-strings-canary-abcdefg\tword\n", "clean.txt",
                    self.clean(), 0, self.ok("clean.txt", 1, 1209))

    def test_12_an_eight_character_tail_is_a_canary_and_cannot_be_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, "barred-strings-canary-abcdefgh\tword\n",
                      {"clean.txt": self.clean()})
            got = run_cli(["--list", "list.txt"] + CTRL + ["clean.txt"], cwd=tmp)
        self.assertEqual(got, (2, "", "cannot run: entry 1 is a canary and cannot carry "
                                      "the word flag\n"))

    def test_13_an_entry_may_start_with_a_slash(self):
        self.expect("/opt\n", "clean.txt", self.clean(), 0, self.ok("clean.txt", 1, 1209))

    def test_14_a_block_comment_over_several_lines_is_removed(self):
        self.expect(self.l1(), "block.ts", padded(["/* a", "moonshot", "b */"]), 0,
                    self.ok("block.ts", 5, 1176), extra=["--strip-comments"])

    def test_15_a_lone_cr_ends_a_line_comment(self):
        content = PAD_LINE * 12 + "// x\rrockstar ninja here\n" + PAD_LINE * 12
        self.expect(self.l1(), "crline.txt", content, 1,
                    self.fail_text("crline.txt", 2, 14), extra=["--strip-comments"])

    def test_16_lone_crs_inside_a_block_comment_are_line_breaks(self):
        content = (PAD_LINE * 12 + "/* a\rb */\rrockstar ninja here\n" + PAD_LINE * 12)
        self.expect(self.l1(), "crblock.txt", content, 1,
                    self.fail_text("crblock.txt", 2, 15), extra=["--strip-comments"])

    def test_17_escaped_quotes_stay_inside_a_note_value(self):
        self.expect(self.l1(), "esc.ts",
                    padded(['x = { note: "say \\"moonshot\\"" };']), 0,
                    self.ok("esc.ts", 5, 1191), extra=["--strip-comments"])

    def test_18_a_key_ending_in_note_is_not_note(self):
        self.expect(self.l1(), "mynote.ts", padded(['x = { my_note: "moonshot" };']), 1,
                    self.fail_text("mynote.ts", 4), extra=["--strip-comments"])

    def test_19_the_note_key_is_case_sensitive(self):
        self.expect(self.l1(), "capnote.ts", padded(['x = { Note: "moonshot" };']), 1,
                    self.fail_text("capnote.ts", 4), extra=["--strip-comments"])

    def test_20_a_concatenation_continues_over_a_line_break(self):
        self.expect(self.l1(), "plusnl.ts", padded(['x = { note: "a"', '+ "moonshot" };']),
                    0, self.ok("plusnl.ts", 5, 1191), extra=["--strip-comments"])

    def test_21_three_strings_concatenated_are_one_value(self):
        self.expect(self.l1(), "three.ts",
                    padded(['x = { note: "a" + "b" + "moonshot" };']), 0,
                    self.ok("three.ts", 5, 1191), extra=["--strip-comments"])

    def test_22_blocks_are_removed_before_line_comments(self):
        self.expect(self.l1(), "lineinblock.ts", padded(["/* x // y */ moonshot"]), 1,
                    self.fail_text("lineinblock.ts", 4), extra=["--strip-comments"])

    def test_23_only_a_name_ending_in_pdf_is_a_pdf(self):
        self.expect(self.l1(), "notes.pdf.txt",
                    padded(["We wrote tests for the importer."]), 0,
                    self.ok("notes.pdf.txt", 5, 1209))

    def test_24_a_symbolic_link_to_the_list_is_the_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, self.l1(), {})
            os.symlink("list.txt", os.path.join(tmp, "ll.txt"))
            got = run_cli(["--list", "list.txt"] + CTRL + ["--min-chars", "0", "ll.txt"],
                          cwd=tmp)
        self.assertEqual(got, (2, "DEAD  file #1: control not found\n", ""))

    def test_25_a_directory_named_for_an_entry_fails_by_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, self.l1(), {})
            os.mkdir(os.path.join(tmp, "moonshot"))
            write(os.path.join(tmp, "moonshot", "clean.txt"), self.clean())
            got = run_cli(["--list", "list.txt"] + CTRL + ["moonshot/clean.txt"], cwd=tmp)
        self.assertEqual(got, (1, "FAIL  file #1: 1 entries\n"
                                  "file #1:0: entry #4 (file name)\n", ""))

    def test_26_a_lone_dash_is_a_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, self.l1(), {})
            got = run_cli(["--list", "list.txt"] + CTRL + ["-"], cwd=tmp)
        self.assertEqual(got, (2, "DEAD  -: cannot read\n", ""))

    def test_27_the_control_is_matched_after_folding(self):
        self.expect(self.l1(), "nbspctl.txt",
                    FILLER_LINE * 12 + "Example Corp shipped it.\n", 0,
                    self.ok("nbspctl.txt", 5, 757))

    def test_28_min_chars_with_leading_zeros_is_read_by_value(self):
        self.assertRun(["--list", L1] + CTRL + ["--min-chars", "0" * 30 + "5", "clean.txt"],
                       0, OK_CLEAN)

    def test_29_min_chars_of_18_digits_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make(tmp, self.l1(), {"clean.txt": self.clean()})
            got = run_cli(["--list", "list.txt"] + CTRL
                          + ["--min-chars", "9" * 18, "clean.txt"], cwd=tmp)
        self.assertEqual(got, (2, "DEAD  clean.txt: too short (1209 chars, minimum "
                                  + "9" * 18 + ")\n", ""))

    def test_30_min_chars_of_19_digits_cannot_run(self):
        code, out, err = run_cli(["--list", L1] + CTRL + ["--min-chars", "1" + "0" * 18,
                                                           "clean.txt"])
        self.assertEqual((code, out, err),
                         (2, "", "cannot run: --min-chars is too large (at most 18 digits)\n"))

    def test_31_min_chars_of_5000_digits_cannot_run_and_never_crashes(self):
        code, out, err = run_cli(["--list", L1] + CTRL + ["--min-chars", "9" * 5000,
                                                           "clean.txt"])
        self.assertEqual((code, out, err),
                         (2, "", "cannot run: --min-chars is too large (at most 18 digits)\n"))
        self.assertNotIn("Traceback", err)


class FixturesCase(unittest.TestCase):
    def test_generator_output_matches_the_committed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fx")
            proc = subprocess.run(
                [sys.executable, "-B", os.path.join(FX, "make_fixtures.py"), out],
                env=clean_env(), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, b"", b""))
            made = sorted(os.listdir(out))
            held = sorted(n for n in os.listdir(FX)
                          if n != "make_fixtures.py" and not n.startswith("__"))
            self.assertEqual(made, held)
            for name in made:
                self.assertEqual(read(os.path.join(out, name)), read(os.path.join(FX, name)),
                                 name)

    def test_every_fixture_the_spec_names_exists(self):
        names = ("plain case wrap hyph hyphcrlf hyphcr hyphsp soft zw nbsp lig emdash clean "
                 "endash compound note nbhyph two substr early bom short nocontrol "
                 "fold trim word word2 decomp lrm canary moonshot-notes moonshot-plain "
                 "moonshot-short prefix-notes strip").split()
        for name in names:
            self.assertTrue(os.path.isfile(os.path.join(FX, name + ".txt")), name)
        for name in ("src lines nlnote url footnote spcolon single unterm strblock "
                     "value").split():
            self.assertTrue(os.path.isfile(os.path.join(FX, name + ".ts")), name)
        for name in (L1, L2, "sample.pdf"):
            self.assertTrue(os.path.isfile(os.path.join(FX, name)), name)

    def test_every_committed_fixture_is_utf8(self):
        with self.assertRaises(UnicodeDecodeError):
            BADUTF8.decode("utf-8")
        root = os.path.join(ROOT, "tests", "fixtures")
        checked = 0
        bad = []
        for folder, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                try:
                    read(os.path.join(folder, name)).decode("utf-8")
                except UnicodeDecodeError:
                    bad.append(os.path.relpath(os.path.join(folder, name), root))
                checked += 1
        self.assertEqual(bad, [])
        self.assertGreaterEqual(checked, 80)
        self.assertFalse(os.path.exists(os.path.join(FX, "badutf8.txt")))



CLEAN = read(os.path.join(FX, "clean.txt"))
TWO = read(os.path.join(FX, "two.txt"))
L1_PATH = os.path.join(FX, L1)
DEAD_READ = "DEAD  file #1: cannot read\n"


def temp_run(files, extra=(), list_text=None):
    """Write each (name, bytes) into a temp directory and run the command there.

    Names are passed relative, as given. With list_text, the list is list.txt in that
    directory; otherwise it is L1 by absolute path."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in files:
            write(os.path.join(tmp, name), content)
        if list_text is None:
            list_args = ["--list", L1_PATH]
        else:
            write(os.path.join(tmp, "list.txt"), list_text)
            list_args = ["--list", "list.txt"]
        return run_cli(list_args + ["--control", "Example Corp"] + list(extra)
                       + [name for name, _content in files], cwd=tmp)


def missing_run(name):
    """Run against a file that does not exist, from the fixtures directory."""
    assert not os.path.exists(os.path.join(FX, name))
    return run_cli(["--list", L1, "--control", "Example Corp", name])


L1_TEXT = read(L1_PATH).decode("utf-8")
SIXTH_ENTRY_LIST = L1_TEXT + "e\\np\n"


class NameFormsCase(RunCase):
    def test_a_name_hyphenated_across_a_line_break_matches(self):
        self.assertEqual(
            temp_run([("moon-\nshot.txt", CLEAN)]),
            (1, "FAIL  file #1: 1 entries\nfile #1:0: entry #4 (file name)\n", ""))

    def test_a_missing_file_with_a_rejoined_matching_name_keeps_the_label_rule(self):
        self.assertEqual(missing_run("moon-\nshot-absent.txt"), (2, DEAD_READ, ""))

    def test_matching_uses_the_path_as_given(self):
        self.assertEqual(missing_run("fix\tit-absent.txt"), (2, DEAD_READ, ""))

    def test_a_printed_path_that_matches_an_entry_is_a_finding(self):
        self.assertEqual(
            temp_run([("re\nport.txt", CLEAN)], list_text=SIXTH_ENTRY_LIST),
            (1, "FAIL  file #1: 1 entries\nfile #1:0: entry #6 (file name)\n", ""))

    def test_the_same_entry_without_an_escape_is_ok(self):
        self.assertEqual(
            temp_run([("report.txt", CLEAN)], list_text=SIXTH_ENTRY_LIST),
            (0, "OK    report.txt: 0 of 6 entries (control found; 1209 chars)\n", ""))


class PrintedPathCase(RunCase):
    def test_a_line_feed_cannot_forge_a_line(self):
        code, out, err = temp_run([("clean\nOK    forged.txt", CLEAN)])
        self.assertEqual(
            (code, out, err),
            (0, "OK    clean\\nOK    forged.txt: 0 of 5 entries (control found; 1209 chars)\n",
             ""))
        self.assertEqual(len(out.splitlines()), 1)

    def test_a_backslash_is_doubled(self):
        self.assertEqual(
            temp_run([("a\\b.txt", CLEAN)]),
            (0, "OK    a\\\\b.txt: 0 of 5 entries (control found; 1209 chars)\n", ""))

    def test_a_direction_override_is_escaped(self):
        self.assertEqual(
            temp_run([("notes\u202etxt.md", CLEAN)]),
            (0, "OK    notes\\u202etxt.md: 0 of 5 entries (control found; 1209 chars)\n", ""))

    def test_fail_and_finding_lines_use_the_printed_path(self):
        self.assertEqual(
            temp_run([("two\n.txt", TWO)]),
            (1, "FAIL  two\\n.txt: 2 entries\ntwo\\n.txt:13: entry #1 (2 x)\n"
                "two\\n.txt:13: entry #2 (1 x)\n", ""))

    def test_each_escape_on_a_dead_line(self):
        rows = [
            ("a\tb.txt", "a\\tb.txt"),
            ("a\rb.txt", "a\\rb.txt"),
            ("a\x01b.txt", "a\\x01b.txt"),
            ("a\x1bb.txt", "a\\x1bb.txt"),
            ("a\x7fb.txt", "a\\x7fb.txt"),
            ("a\x85b.txt", "a\\x85b.txt"),
            ("a\x9fb.txt", "a\\x9fb.txt"),
            ("a\u2028b.txt", "a\\u2028b.txt"),
            ("a\u2029b.txt", "a\\u2029b.txt"),
            ("a\ufeffb.txt", "a\\ufeffb.txt"),
            ("a\U000e0001b.txt", "a\\U000e0001b.txt"),
            ("a\\\nb.txt", "a\\\\\\nb.txt"),
        ]
        for name, printed in rows:
            with self.subTest(name=name):
                self.assertEqual(missing_run(name),
                                 (2, "DEAD  " + printed + ": cannot read\n", ""))

    def test_a_nul_is_escaped(self):
        result = barred.run(list_path=os.path.join(FX, L1), files=["a\x00b.txt"],
                            controls=["Example Corp"])
        self.assertEqual(result.exit_code, 2)
        self.assertTrue(result.ran)
        self.assertEqual(result.text, "DEAD  a\\x00b.txt: cannot read\n")

    def test_other_characters_print_as_given(self):
        for name in ["caf\u00e9\u00a0\U0001f600.txt", "a b-c.txt"]:
            with self.subTest(name=name):
                self.assertEqual(missing_run(name),
                                 (2, "DEAD  " + name + ": cannot read\n", ""))


class Revision4NothingBarredIsPrintedCase(RunCase):
    def test_new_name_runs_print_no_entry_and_no_matching_name(self):
        code1, out1, err1 = temp_run([
            ("moon-\nshot.txt", CLEAN),
            ("clean\nOK    forged.txt", CLEAN),
            ("a\\b.txt", CLEAN),
            ("notes\u202etxt.md", CLEAN),
            ("two\n.txt", TWO),
        ])
        code2, out2, err2 = temp_run([("re\nport.txt", CLEAN)], list_text=SIXTH_ENTRY_LIST)
        seen1 = (out1 + err1).lower()
        seen2 = (out2 + err2).lower()
        for entry in L1_ENTRIES:
            self.assertFalse(contains_entry(seen1, entry, False), entry)
            self.assertFalse(contains_entry(seen2, entry, False), entry)
        self.assertFalse(contains_entry(seen2, "e\\np", False))
        for name in ["moon-\nshot.txt", "moon-\\nshot.txt"]:
            self.assertNotIn(name, out1 + err1)
        for name in ["re\nport.txt", "re\\nport.txt"]:
            self.assertNotIn(name, out2 + err2)
        self.assertTrue(contains_entry("re\\nport.txt", "e\\np", False))


class Revision4MinCharsCase(RunCase):
    def test_the_revision_4_known_answers(self):
        base = ["--list", "list-l1.txt", "--control", "Example Corp"]
        self.assertEqual(
            run_cli(base + ["--min-chars", "1000000000000000000", "clean.txt"]),
            (2, "", "cannot run: --min-chars is too large (at most 18 digits)\n"))
        self.assertEqual(
            run_cli(base + ["--min-chars", "999999999999999999", "clean.txt"]),
            (2, "DEAD  clean.txt: too short (1209 chars, minimum 999999999999999999)\n", ""))
        self.assertEqual(
            run_cli(base + ["--min-chars", "0000000000000000000500", "clean.txt"]),
            (0, OK_CLEAN, ""))


class LayoutCase(unittest.TestCase):
    def test_the_main_guard_is_the_last_statement(self):
        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        guard = ast.dump(ast.parse('__name__ == "__main__"', mode="eval").body)
        guards = [i for i, node in enumerate(tree.body)
                  if isinstance(node, ast.If) and ast.dump(node.test) == guard]
        self.assertEqual(guards, [len(tree.body) - 1])


if __name__ == "__main__":
    unittest.main()
