"""Tests for ``track-record wrapped-compounds`` that need no PDF (spec: docs/specs/wrapped-compounds.md).

Text cases W3 to W11, W14 and W15 call the pure function with literal texts (L is the layout
text, D the default text, ``\\f`` a form feed); the cases of section 10 that name no D get a
D of the same words joined, because the function refuses a default text with no letter. The
command-line cases run the command in a child process on arguments and non-PDF files only:
the PDF cases are in tests/test_wrapped_compounds_pdf.py. All data here is invented. No
raw invisible character appears in this file; special characters are built with chr().
"""

import io
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SPEC = os.path.join(ROOT, "docs", "specs", "wrapped-compounds.md")
GUIDE = os.path.join(ROOT, "docs", "guides", "wrapped-compounds.md")
MODULE = os.path.join(SRC, "career_track_record", "wrapped_compounds.py")
sys.path.insert(0, SRC)

from career_track_record import cli, wrapped_compounds as wc  # noqa: E402

SOFT_HYPHEN = chr(0xAD)
FULLWIDTH_HYPHEN = chr(0xFF0D)
SMALL_HYPHEN = chr(0xFE63)
LIGATURE_FI = chr(0xFB01)
ZERO_WIDTH_SPACE = chr(0x200B)
LINE_SEPARATOR = chr(0x2028)
NEXT_LINE = chr(0x85)
ACUTE = chr(0x301)
E_CIRCUMFLEX = chr(0xEA)
VERTICAL_TAB = chr(0x0B)
EN_DASH = chr(0x2013)
HYPHEN_U2010 = chr(0x2010)

NO_OUTPUT = "cannot run: cannot write output\n"
NOT_A_PDF = "not a PDF; give the PDF file"


def find(layout, default):
    """The function under test, called with the spec's L and D (it takes D first)."""
    return wc.find_wrapped_compounds(default, layout)


def shape(hits):
    return [(h.page, h.line, h.compound, h.token, h.marker) for h in hits]


def dead_reason(layout, default):
    try:
        find(layout, default)
    except wc.Dead as dead:
        return dead.reason
    raise AssertionError("no Dead raised")


def env(extra=None):
    e = dict(os.environ)
    for name in ("BARRED_STRINGS_PATH", "BARRED_STRINGS", "CTR_CONFIG_DIR", "XDG_CONFIG_HOME"):
        e.pop(name, None)
    e["PYTHONPATH"] = SRC
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def run_cli(args, cwd=ROOT, env_extra=None, command="wrapped-compounds"):
    proc = subprocess.run([sys.executable, "-m", "career_track_record", command] + list(args),
                          cwd=cwd, env=env(env_extra), stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def spec_synopsis():
    """The fenced block under ``## 2. Synopsis`` of the spec file, read from the file."""
    with open(SPEC, encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("\n## 2. Synopsis\n")
    fence = text.index("```text\n", start) + len("```text\n")
    return text[fence:text.index("\n```", fence)] + "\n"


# ---------------------------------------------------------------- the spec's text cases

class TextCases(unittest.TestCase):
    def test_w3_unicode_letters(self):
        hits = find("bien-\n" + E_CIRCUMFLEX + "tre\n",
                    "bien" + E_CIRCUMFLEX + "tre\n")
        self.assertEqual(shape(hits), [(1, 1, "bien-" + E_CIRCUMFLEX + "tre",
                                        "bien" + E_CIRCUMFLEX + "tre", "finding")])

    def test_w4_not_letters(self):
        self.assertEqual(find("2026-\n27\n", "202627\n"), [])

    def test_w5_blank_line_between(self):
        self.assertEqual(shape(find("well-\n\n  known\n", "wellknown\n")),
                         [(1, 1, "well-known", "wellknown", "finding")])

    def test_w6_page_edge(self):
        self.assertEqual(find("well-\f known\f", "wellknown\f\f"), [])

    def test_w7_broken_word_appears_once(self):
        self.assertEqual(shape(find("manage-\nment\n", "management\n")),
                         [(1, 1, "manage-ment", "management", "finding")])

    def test_w7a_note_case(self):
        hits = find("manage-\nment\fmanagement\f", "management\fmanagement\f")
        self.assertEqual(shape(hits), [(1, 1, "manage-ment", "management", "note")])
        self.assertEqual(wc.hit_line(hits[0]),
                         '  wrapped compounds: page 1 line 1: "manage-ment" is split across '
                         'lines; extracted text reads "management" (note: "management" also '
                         'appears unwrapped, nothing to fix)')

    def test_w7a_variant_a_token_equal_to_the_compound_makes_it_a_finding(self):
        hits = find("manage-\nment\fmanagement manage-ment\f",
                    "management\fmanagement manage-ment\f")
        self.assertEqual(shape(hits), [(1, 1, "manage-ment", "management", "finding")])

    def test_w8_default_keeps_the_hyphen(self):
        hits = find("well-\nknown\n", "well-known\n")
        self.assertEqual(shape(hits), [(1, 1, "well-known", None, "nojoin")])
        self.assertEqual(wc.hit_line(hits[0]),
                         '  wrapped compounds: page 1 line 1: "well-known" is split across '
                         'lines; extracted text does not join it (no join found, not a '
                         'finding)')

    def test_w9_two_columns_pinned(self):
        # Known limit: in a page of two columns the hyphen is not at the end of the layout
        # line, so the wrap is missed (spec section 8). If a later fix finds it, this case
        # changes on purpose.
        self.assertEqual(find("alpha well-     beta\nknown gamma\n", "alpha wellknown beta gamma\n"),
                         [])

    def test_w10_soft_hyphen(self):
        self.assertEqual(find("well" + SOFT_HYPHEN + "\nknown\n", "wellknown\n"), [])

    def test_w11_same_pair_twice_one_join(self):
        hits = find("well-\nknown a\nwell-\nknown b\n", "wellknown a well-known b\n")
        self.assertEqual(shape(hits), [(1, 1, "well-known", "wellknown", "finding"),
                                       (1, 3, "well-known", None, "nojoin")])
        self.assertTrue(wc.hit_line(hits[0]).endswith('reads "wellknown" (finding)'))
        self.assertTrue(wc.hit_line(hits[1]).endswith("(no join found, not a finding)"))

    def test_w14_chained_left_half_and_punctuation(self):
        hits = find("the state-of-the-\nart, today\n", "the state-of-theart, today\n")
        self.assertEqual(shape(hits), [(1, 1, "state-of-the-art", "state-of-theart", "finding")])
        self.assertIn('"state-of-the-art" is split across lines; extracted text reads '
                      '"state-of-theart" (finding)', wc.hit_line(hits[0]))

    def test_w15_fullwidth_hyphen_minus(self):
        for dash in (FULLWIDTH_HYPHEN, SMALL_HYPHEN):
            with self.subTest(dash=hex(ord(dash))):
                hits = find("well" + dash + "\nknown\n", "wellknown\n")
                self.assertEqual(shape(hits), [(1, 1, "well-known", "wellknown", "finding")])


# ---------------------------------------------------------------- one test per condition

class ConditionCases(unittest.TestCase):
    def test_a_digit_before_the_hyphen_is_not_a_wrap_line(self):
        self.assertEqual(find("abc1-\nknown\n", "abc1known\n"), [])

    def test_a_next_line_that_starts_with_a_digit_is_not_a_wrap(self):
        self.assertEqual(find("well-\n5known\n", "well5known\n"), [])

    def test_a_next_line_that_starts_with_punctuation_is_not_a_wrap(self):
        for start in (".", "-", "(", chr(0x2014)):
            with self.subTest(start=start):
                self.assertEqual(find("well-\n" + start + "known\n", "wellknown\n"), [])

    def test_a_hyphen_alone_on_a_line_is_not_a_wrap_line(self):
        self.assertEqual(find("-\nknown\n", "known\n"), [])

    def test_a_combining_mark_after_a_letter_counts_as_a_letter(self):
        # x and an acute accent have no single-character form, so NFKC leaves the mark.
        hits = find("x" + ACUTE + "-\nknown\n", "x" + ACUTE + "known\n")
        self.assertEqual(shape(hits), [(1, 1, "x" + ACUTE + "-known", "x" + ACUTE + "known",
                                        "finding")])

    def test_a_combining_mark_that_follows_no_letter_does_not_count(self):
        self.assertEqual(find(" " + ACUTE + "-\nknown\n", "known\n"), [])
        self.assertEqual(find("well-\n" + ACUTE + "known\n", "wellknown\n"), [])

    def test_the_right_half_takes_a_mark_that_follows_its_letter(self):
        hits = find("well-\nx" + ACUTE + "y, z\n", "wellx" + ACUTE + "y z\n")
        self.assertEqual(hits[0].compound, "well-x" + ACUTE + "y")

    def test_a_right_half_shorter_than_three_joins_on_its_whole_length(self):
        hits = find("well-\nab, c\n", "wellab\n")
        self.assertEqual(shape(hits), [(1, 1, "well-ab", "wellab", "finding")])
        self.assertEqual(shape(find("well-\nab, c\n", "wellabc\n"))[0][3], "wellabc")

    def test_a_token_that_matches_only_part_of_a_short_right_half_does_not_join(self):
        hits = find("well-\nab, c\n", "wellaxy\n")
        self.assertEqual(shape(hits), [(1, 1, "well-ab", None, "nojoin")])

    def test_a_right_half_of_three_or_more_joins_on_its_first_three_letters_only(self):
        hits = find("well-\nknown a\n", "wellknox\n")
        self.assertEqual(shape(hits), [(1, 1, "well-known", "wellknox", "finding")])
        self.assertEqual(shape(find("well-\nknown a\n", "wellknx\n")),
                         [(1, 1, "well-known", None, "nojoin")])

    def test_the_right_half_stops_at_a_hyphen(self):
        hits = find("cross-\nteam-based work\n", "crossteam-based work\n")
        self.assertEqual(shape(hits), [(1, 1, "cross-team", "crossteam-based", "finding")])

    def test_the_left_half_stops_at_a_digit_and_drops_a_leading_hyphen(self):
        self.assertEqual(find("abc2def-\nghi\n", "abc2defghi\n")[0].compound, "def-ghi")
        self.assertEqual(find("x -well-\nknown\n", "x wellknown\n")[0].compound, "well-known")

    def test_other_dashes_are_not_read(self):
        for dash in (EN_DASH, HYPHEN_U2010, chr(0x2014)):
            with self.subTest(dash=hex(ord(dash))):
                self.assertEqual(find("well" + dash + "\nknown\n", "wellknown\n"), [])

    def test_whitespace_after_the_hyphen_is_trailing_whitespace(self):
        for tail in ("   ", "\t", " \t "):
            with self.subTest(tail=tail):
                self.assertEqual(len(find("well-" + tail + "\nknown\n", "wellknown\n")), 1)

    def test_a_format_character_is_removed_before_the_line_end_is_read(self):
        hits = find("well-" + ZERO_WIDTH_SPACE + "\nknown\n", "wellknown\n")
        self.assertEqual(len(hits), 1)

    def test_case_differences_join_and_the_compound_keeps_its_case(self):
        hits = find("Well-\nKNOWN\n", "wellknown\n")
        self.assertEqual(shape(hits), [(1, 1, "Well-KNOWN", "wellknown", "finding")])
        hits = find("well-\nknown\n", "WELLKNOWN\n")
        self.assertEqual(shape(hits), [(1, 1, "well-known", "WELLKNOWN", "finding")])

    def test_a_ligature_shows_folded_in_the_printed_hit(self):
        hits = find(LIGATURE_FI + "ne-\ntuned\n", LIGATURE_FI + "netuned\n")
        self.assertEqual(shape(hits), [(1, 1, "fine-tuned", "finetuned", "finding")])

    def test_a_no_break_space_is_a_space(self):
        hits = find("so well-\nknown\n".replace(" ", chr(0xA0)), "so wellknown\n")
        self.assertEqual(shape(hits), [(1, 1, "well-known", "wellknown", "finding")])


class PageAndLineCases(unittest.TestCase):
    def test_a_hit_on_page_two_is_numbered_from_the_top_of_its_page(self):
        hits = find("x\fa\n\nwell-\n\nknown\f", "x\fa wellknown\f")
        self.assertEqual(shape(hits), [(2, 3, "well-known", "wellknown", "finding")])

    def test_blank_lines_count_in_the_line_number(self):
        self.assertEqual(find("a\n\n   \nwell-\nknown\n", "a wellknown\n")[0].line, 4)

    def test_a_wrap_followed_only_by_blank_lines_is_the_last_on_its_page(self):
        self.assertEqual(find("well-\n\n\f known\f", "wellknown\f\f"), [])

    def test_the_page_count_of_each_text_ends_at_the_last_form_feed_once(self):
        # "a\fb\f" is two pages; "a\fb\f\f" is three, the last one empty.
        self.assertEqual(find("a\fb\f", "a\fb\f"), [])
        self.assertEqual(dead_reason("a\fb\f\f", "a\fb\f"),
                         "page counts differ (default 2, layout 3); export the PDF again")

    def test_the_page_count_dead_reason_is_worded_by_the_spec(self):
        self.assertEqual(dead_reason("well-\fknown\f", "wellknown\n"),
                         "page counts differ (default 1, layout 2); export the PDF again")

    def test_a_page_of_the_default_text_is_read_for_its_own_wraps_only(self):
        # The token "wellknown" is on page 1 only: page 2's wrap finds no token.
        hits = find("x\fwell-\nknown\n", "wellknown\fx\f")
        self.assertEqual(shape(hits), [(2, 1, "well-known", None, "nojoin")])

    def test_the_first_free_token_is_taken_per_page(self):
        hits = find("well-\nknown\fwell-\nknown\f", "wellknown\fwellknown\f")
        self.assertEqual([h.token for h in hits], ["wellknown", "wellknown"])

    def test_lf_crlf_and_lone_cr_each_end_a_line(self):
        for ending in ("\n", "\r\n", "\r"):
            with self.subTest(ending=repr(ending)):
                hits = find("a" + ending + "well-" + ending + "known" + ending, "a wellknown\n")
                self.assertEqual(shape(hits), [(1, 2, "well-known", "wellknown", "finding")])

    def test_a_vertical_tab_or_line_separator_inside_a_line_does_not_end_it(self):
        for odd in (VERTICAL_TAB, LINE_SEPARATOR, NEXT_LINE, chr(0x1C), chr(0x2029)):
            with self.subTest(odd=hex(ord(odd))):
                self.assertEqual(find("well-" + odd + "known\n", "wellknown\n"), [])
                hits = find("alpha" + odd + "beta\nwell-\nknown\n", "alpha wellknown\n")
                self.assertEqual([h.line for h in hits], [2])

    def test_a_separator_character_ending_the_text_is_trailing_whitespace(self):
        hits = find("well-" + LINE_SEPARATOR + "\nknown\n", "wellknown\n")
        self.assertEqual(len(hits), 1)


class MarkerCases(unittest.TestCase):
    def test_a_note_needs_both_conditions(self):
        # Neither condition: the word appears once -> finding (W7).
        self.assertEqual(find("manage-\nment\n", "management\n")[0].marker, "finding")
        # Condition 1 only: another unwrapped copy, and no token reads manage-ment -> note.
        self.assertEqual(find("manage-\nment\n", "management management\n")[0].marker, "note")
        # Condition 1 and a token equal to the compound on another page -> finding.
        hits = find("manage-\nment\fx\f", "management management\fmanage-ment\f")
        self.assertEqual(hits[0].marker, "finding")
        # The compound's case does not matter for condition 2.
        hits = find("manage-\nment\fx\f", "management management\fMANAGE-ment\f")
        self.assertEqual(hits[0].marker, "finding")

    def test_a_token_taken_by_two_wraps_leaves_no_unwrapped_copy(self):
        hits = find("manage-\nment\nmanage-\nment\n", "management management\n")
        self.assertEqual([h.marker for h in hits], ["finding", "finding"])

    def test_the_note_case_counts_across_all_pages(self):
        hits = find("manage-\nment\fx\fy\f", "management\fx\fmanagement\f")
        self.assertEqual(hits[0].marker, "note")

    def test_a_no_join_hit_is_never_a_note(self):
        hits = find("well-\nknown\n", "well-known wellknx\n")
        self.assertEqual(hits[0].marker, "nojoin")


class DeadCases(unittest.TestCase):
    def test_no_text_is_a_default_text_with_no_letter_or_digit_after_step_one(self):
        reason = ("no text; the PDF holds no selectable text (a scan?), so export it again "
                  "from the document")
        for default in ("", "\n", " \f \f", "-- .. !! \n", ZERO_WIDTH_SPACE + "\n",
                        chr(0xA0) * 3):
            with self.subTest(default=repr(default)):
                self.assertEqual(dead_reason("well-\nknown\n", default), reason)

    def test_a_default_text_of_one_digit_has_text(self):
        self.assertEqual(find("7\n", "7\n"), [])

    def test_no_text_wins_over_no_layout_text_and_over_the_page_count(self):
        self.assertTrue(dead_reason("", "").startswith("no text; "))
        self.assertTrue(dead_reason("!!\f!!\f", "!!\n").startswith("no text; "))

    def test_no_layout_text_is_a_layout_text_with_no_letter_or_digit_after_step_one(self):
        for layout in ("", "\n", "--\n", "..\f..\f", ZERO_WIDTH_SPACE):
            with self.subTest(layout=repr(layout)):
                self.assertEqual(dead_reason(layout, "well\n"),
                                 "no layout text; export the PDF again")

    def test_a_layout_text_of_one_digit_has_layout_text(self):
        self.assertEqual(find("7\n", "well\n"), [])

    def test_no_layout_text_comes_before_the_page_count(self):
        self.assertEqual(dead_reason("!!\n", "ab\fcd\f"),
                         "no layout text; export the PDF again")

    def test_a_digit_counts_as_text_by_category_nd_not_by_isdigit(self):
        # U+00B2 (superscript two) is not Nd, and NFKC turns it into the digit 2.
        self.assertEqual(find("well\n", chr(0xB2) + "\n"), [])


class ReturnShapeCases(unittest.TestCase):
    def test_the_return_value_is_a_list_of_five_field_hits_in_order(self):
        hits = find("well-\nknown\n", "wellknown\n")
        self.assertIsInstance(hits, list)
        self.assertEqual(len(hits), 1)
        self.assertEqual(wc.Hit._fields, ("page", "line", "compound", "token", "marker"))
        self.assertEqual(hits[0]._fields, ("page", "line", "compound", "token", "marker"))
        self.assertEqual(tuple(hits[0]), (1, 1, "well-known", "wellknown", "finding"))
        self.assertEqual(len(tuple(hits[0])), 5)

    def test_the_token_is_none_when_nothing_joined(self):
        self.assertIsNone(find("well-\nknown\n", "well-known\n")[0].token)

    def test_no_wrap_gives_an_empty_list(self):
        self.assertEqual(find("well known\n", "well known\n"), [])

    def test_the_function_takes_the_default_text_first_and_the_layout_text_second(self):
        layout = "well-\nknown\n"
        default = "wellknown\n"
        self.assertEqual(shape(wc.find_wrapped_compounds(default, layout)),
                         [(1, 1, "well-known", "wellknown", "finding")])
        # Swapped, the layout text is read as the default text and the other way round.
        self.assertEqual(wc.find_wrapped_compounds(layout, default), [])
        self.assertNotEqual(wc.find_wrapped_compounds(default, layout),
                            wc.find_wrapped_compounds(layout, default))

    def test_dead_carries_a_reason_and_is_an_exception(self):
        error = wc.Dead("because")
        self.assertEqual(error.reason, "because")
        self.assertIsInstance(error, Exception)

    def test_hits_come_in_page_and_line_order(self):
        hits = find("well-\nknown\na-\nbc\fcross-\nteam\f", "wellknown abc\fcrossteam\f")
        self.assertEqual([(h.page, h.line) for h in hits], [(1, 1), (1, 3), (2, 1)])


# ---------------------------------------------------------------- the command line

class HelpCases(unittest.TestCase):
    def test_help_is_the_fenced_block_of_the_spec_plus_a_newline(self):
        expected = spec_synopsis()
        self.assertTrue(expected.startswith("usage: track-record wrapped-compounds --control"))
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag):
                self.assertEqual(run_cli([flag]), (0, expected, ""))
        self.assertEqual(cli._WRAPPED_HELP, expected)

    def test_help_wins_over_every_other_argument_and_reads_no_file(self):
        expected = spec_synopsis()
        with tempfile.TemporaryDirectory() as tmp:
            rows = [["-h", "--bogus"], ["--bogus", "--help"], ["--control", "-h"],
                    ["--control", "--help"], ["--control"] + ["x"] + ["-h"],
                    ["missing.pdf", "-h"], ["-h", "--control"], ["--control=x", "--help"],
                    ["--control", "--", "--help"], ["--help=1", "-h"], ["--control", "x", "-h", "y"]]
            for args in rows:
                with self.subTest(args=args):
                    self.assertEqual(run_cli(args, cwd=tmp), (0, expected, ""))
                    self.assertEqual(os.listdir(tmp), [])

    def test_help_after_a_double_dash_is_a_file_name(self):
        rows = [(["--", "--help"], (2, "", "cannot run: no --control given\n")),
                (["--help=1"], (2, "", "cannot run: unknown option\n"))]
        for args, expected in rows:
            with self.subTest(args=args):
                self.assertEqual(run_cli(args), expected)
        code, out, err = run_cli(["--control", "x", "--", "--help"])
        self.assertEqual((code, out, err), (2, "DEAD  --help: " + NOT_A_PDF + "\n", ""))

    def test_help_reads_no_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_config(tmp, "not json at all")
            got = run_cli(["--help"], env_extra={"CTR_CONFIG_DIR": tmp})
            self.assertEqual(got, (0, spec_synopsis(), ""))

    @staticmethod
    def write_config(folder, text):
        with open(os.path.join(folder, "config.json"), "w", encoding="utf-8") as handle:
            handle.write(text)


class UsageCases(unittest.TestCase):
    def assertUsage(self, args, line, cwd=ROOT):
        got = run_cli(args, cwd=cwd)
        self.assertEqual(got, (2, "", "cannot run: " + line + "\n"), args)

    def test_each_usage_error_is_one_stderr_line_with_nothing_on_stdout(self):
        rows = [
            (["--bogus"], "unknown option"),
            (["--control"], "--control needs a value"),
            (["--control", "x"], "no input file"),
            (["x.pdf"], "no --control given"),
            (["--control", "", "x.pdf"], "no usable --control given"),
        ]
        for args, line in rows:
            with self.subTest(args=args):
                self.assertUsage(args, line)

    def test_usage_errors_are_checked_in_the_spec_s_order(self):
        rows = [
            # an unknown option outranks everything
            # Known limit: "--control --bogus" takes "--bogus" as the control, as barred
            # does with its own options; the run then lacks a file.
            (["--control", "--bogus"], "no input file"),
            (["--bogus", "--control"], "unknown option"),
            (["--control", "--control", "x", "--bogus"], "unknown option"),
            # a missing value outranks a missing file
            (["--control", "--control", "x"], "--control needs a value"),
            # a missing file outranks a missing control
            ([], "no input file"),
            # a missing control outranks an empty one, and an empty one needs a file first
            (["--control", ""], "no input file"),
            (["--control=", "x.pdf"], "no usable --control given"),
            (["--control", "", "--control", "   ", "x.pdf"], "no usable --control given"),
            (["--control", ZERO_WIDTH_SPACE, "x.pdf"], "no usable --control given"),
        ]
        for args, line in rows:
            with self.subTest(args=args):
                self.assertUsage(args, line)

    def test_a_value_taking_option_with_a_dash_dash_value_takes_it(self):
        # As barred does: "--" in a value's place is the value.
        code, out, err = run_cli(["--control", "--", "x.txt"])
        self.assertEqual((code, out, err), (2, "DEAD  x.txt: " + NOT_A_PDF + "\n", ""))

    def test_the_usage_error_comes_before_any_file_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args in (["--bogus", "missing.pdf"], ["missing.pdf"], ["--control", "",
                                                                      "missing.pdf"]):
                with self.subTest(args=args):
                    code, out, err = run_cli(args, cwd=tmp)
                    self.assertEqual((code, out), (2, ""))
                    self.assertEqual(len(err.splitlines()), 1)
                    self.assertTrue(err.startswith("cannot run: "))
                    self.assertNotIn("missing", err)

    def test_the_command_writes_nothing_into_its_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_cli(["--control", "x", "notes.txt"], cwd=tmp)
            run_cli(["--bogus"], cwd=tmp)
            self.assertEqual(os.listdir(tmp), [])


class OptionParsingCases(unittest.TestCase):
    def parse(self, args):
        return cli._parse_wrapped(args)

    def test_control_equals_text_is_control_text(self):
        self.assertEqual(self.parse(["--control=Example Corp", "a.pdf"]),
                         self.parse(["--control", "Example Corp", "a.pdf"]))
        self.assertEqual(self.parse(["--control=a=b", "f"])["controls"], ["a=b"])

    def test_control_is_repeatable_and_keeps_its_order(self):
        self.assertEqual(self.parse(["--control", "a", "x.pdf", "--control=b"]),
                         {"controls": ["a", "b"], "files": ["x.pdf"]})

    def test_after_a_double_dash_every_argument_is_a_file_name(self):
        self.assertEqual(self.parse(["--control", "a", "--", "--control", "-x", "--"]),
                         {"controls": ["a"], "files": ["--control", "-x", "--"]})

    def test_a_lone_dash_is_a_file_name(self):
        self.assertEqual(self.parse(["--control", "a", "-"]),
                         {"controls": ["a"], "files": ["-"]})
        code, out, err = run_cli(["--control", "a", "-"])
        self.assertEqual((code, out, err), (2, "DEAD  -: " + NOT_A_PDF + "\n", ""))

    def test_a_file_named_like_an_option_after_a_double_dash_is_a_file(self):
        code, out, err = run_cli(["--control", "a", "--", "--bogus", "-h"])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  --bogus: " + NOT_A_PDF + "\nDEAD  -h: " + NOT_A_PDF + "\n")

    def test_help_is_asked_for_wherever_it_stands(self):
        for args in (["-h"], ["a", "--help"], ["--control", "a", "-h"], ["--control", "-h"],
                     ["--bogus", "-h"]):
            with self.subTest(args=args):
                self.assertEqual(self.parse(args), {"help": True})

    def test_an_option_error_raises_the_option_error(self):
        for args in (["--bogus"], ["--control"], ["--control", "--control"]):
            with self.subTest(args=args):
                with self.assertRaises(cli._OptionError):
                    self.parse(args)


class FileCases(unittest.TestCase):
    def test_a_name_that_does_not_end_in_dot_pdf_is_dead(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("notes.txt", "resume.pdfx", "resume", "pdf", "resume.pdf.txt"):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
                    handle.write("Example Corp\n")
                with self.subTest(name=name):
                    self.assertEqual(run_cli(["--control", "Example Corp", name], cwd=tmp),
                                     (2, "DEAD  %s: %s\n" % (name, NOT_A_PDF), ""))

    def test_a_name_that_does_not_exist_and_is_not_a_pdf_is_dead_not_a_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_cli(["--control", "x", "missing.txt"], cwd=tmp),
                             (2, "DEAD  missing.txt: " + NOT_A_PDF + "\n", ""))

    def test_every_file_gets_a_status_line_in_argument_order(self):
        names = ["c.txt", "a.txt", "b.doc"]
        code, out, err = run_cli(["--control", "x"] + names)
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "".join("DEAD  %s: %s\n" % (n, NOT_A_PDF) for n in names))

    def test_a_path_with_a_newline_is_printed_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = "a\nb\\c.txt"
            code, out, err = run_cli(["--control", "x", name], cwd=tmp)
            self.assertEqual((code, err), (2, ""))
            self.assertEqual(out, "DEAD  a\\nb\\\\c.txt: " + NOT_A_PDF + "\n")
            self.assertEqual(len(out.splitlines()), 1)

    def test_a_path_is_always_printed_and_never_replaced_by_a_number(self):
        code, out, err = run_cli(["--control", "x", "turnkey-synergy.txt"])
        self.assertIn("turnkey-synergy.txt", out)
        self.assertNotIn("file #", out)

    def test_stdout_closed_gives_one_line_and_exit_2(self):
        proc = subprocess.run(
            ["/bin/sh", "-c", 'exec "$0" "$@" >&-', sys.executable, "-m", "career_track_record",
             "wrapped-compounds", "--control", "x", "notes.txt"],
            cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr.decode("utf-8")),
                         (2, b"", NO_OUTPUT))

    def test_a_stdout_with_no_reader_gives_one_line_and_exit_2(self):
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "career_track_record", "wrapped-compounds", "--control",
                 "x", "notes.txt"], cwd=ROOT, env=env(), stdin=subprocess.DEVNULL,
                stdout=write_end, stderr=subprocess.PIPE)
        finally:
            os.close(write_end)
        self.assertEqual((proc.returncode, proc.stderr.decode("utf-8")), (2, NO_OUTPUT))

    def test_the_run_function_in_process_returns_the_text_and_the_code(self):
        result = wc.run(files=["a.txt"], controls=["x"])
        self.assertEqual((result.exit_code, result.ran, result.error),
                         (2, True, ""))
        self.assertEqual(result.text, "DEAD  a.txt: " + NOT_A_PDF + "\n")
        result = wc.run(files=[], controls=["x"])
        self.assertEqual((result.exit_code, result.ran, result.text, result.error),
                         (2, False, "", "cannot run: no input file"))


class NoConfigurationCases(unittest.TestCase):
    """The command reads no configuration file and nothing from the setup configuration."""

    def test_a_config_set_up_as_the_other_commands_tests_do_changes_nothing(self):
        cases = [
            (["--control", "x", "notes.txt"], (2, "DEAD  notes.txt: " + NOT_A_PDF + "\n", "")),
            (["--control", "x"], (2, "", "cannot run: no input file\n")),
            (["notes.txt"], (2, "", "cannot run: no --control given\n")),
        ]
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            for raw in ("not json at all", '{"config-version": 1, "record-folder": "' +
                        tmp.replace("\\", "\\\\") + '"}'):
                with open(os.path.join(tmp, "config.json"), "w", encoding="utf-8") as handle:
                    handle.write(raw)
                extra = {"CTR_CONFIG_DIR": tmp, "HOME": home,
                         "BARRED_STRINGS_PATH": os.path.join(tmp, "missing-list.txt")}
                for args, expected in cases:
                    with self.subTest(raw=raw[:12], args=args):
                        self.assertEqual(run_cli(args, cwd=home, env_extra=extra), expected)
                        self.assertEqual(run_cli(args, cwd=home), expected)

    def test_the_same_unusable_config_does_stop_barred_so_the_probe_can_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "config.json"), "w", encoding="utf-8") as handle:
                handle.write("not json at all")
            code, out, err = run_cli(["--control", "x", "notes.txt"], command="barred",
                                     env_extra={"CTR_CONFIG_DIR": tmp})
            self.assertEqual(code, 2)
            self.assertIn("config is not usable", err)

    def test_the_module_names_no_config_and_no_environment(self):
        with open(MODULE, encoding="utf-8") as handle:
            source = handle.read()
        for word in ("config", "environ", "getenv", "write_guard", "record_folder"):
            self.assertNotIn(word, source)


class SourceCases(unittest.TestCase):
    def test_wrapped_compounds_py_holds_no_subprocess(self):
        with open(MODULE, encoding="utf-8") as handle:
            self.assertNotIn("subprocess", handle.read())

    def test_the_module_reads_both_modes_through_pdf_text_only(self):
        with open(MODULE, encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(source.count("pdf_text.pdf_text("), 1)
        self.assertIn("layout=layout", source)

    def test_the_cli_spec_lists_the_command_in_the_help_list_once(self):
        with open(os.path.join(ROOT, "docs", "specs", "cli.md"), encoding="utf-8") as handle:
            text = handle.read()
        line = "- wrapped-compounds: find hyphenated words split across two lines in a PDF\n"
        self.assertEqual(text.count(line), 1)
        self.assertLess(text.index("- drafts: check a file"), text.index(line))

    def test_the_spec_file_names_its_revision_and_carries_the_signed_block(self):
        with open(SPEC, encoding="utf-8") as handle:
            text = handle.read()
        self.assertRegex(text, re.compile(r"^Revision: 6\. ", re.M))
        self.assertIn("signed by the method owner", text)
        self.assertEqual(text.count("<!-- signed spec begins: sha256 "), 1)
        self.assertEqual(text.count("<!-- signed spec ends -->"), 1)


class GuideCases(unittest.TestCase):
    SENTENCE = ("A word your word processor broke at the end of a line, such as manage- / ment, "
                "looks the same as a wrapped compound. If the joined word also appears "
                "unbroken elsewhere in the file, the line is a note, not a finding. To clear "
                "both, turn off automatic hyphenation or widen the line so the word doesn't "
                "wrap.")

    def guide(self):
        with open(GUIDE, encoding="utf-8") as handle:
            return handle.read()

    def test_the_guide_holds_the_section_8_sentence_word_for_word(self):
        self.assertEqual(self.guide().count(self.SENTENCE), 1)

    def test_the_guide_holds_one_example_of_each_of_the_three_markers(self):
        text = self.guide()
        examples = [
            '  wrapped compounds: page 1 line 14: "well-known" is split across lines; '
            'extracted text reads "wellknown" (finding)',
            '  wrapped compounds: page 2 line 3: "cross-team" is split across lines; '
            'extracted text does not join it (no join found, not a finding)',
            '  wrapped compounds: page 2 line 9: "manage-ment" is split across lines; '
            'extracted text reads "management" (note: "management" also appears unwrapped, '
            'nothing to fix)',
        ]
        for example in examples:
            with self.subTest(example=example[:50]):
                self.assertEqual(text.count(example), 1)

    def test_the_guide_states_the_known_limits_and_that_exit_2_is_not_a_pass(self):
        text = self.guide()
        for phrase in ("two or more columns", "soft hyphen", "hyphen-minus",
                       "shorter than 3 letters", "2 is not a pass", "checks nothing else"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_guide_names_no_private_tooling(self):
        text = self.guide().lower()
        self.assertNotIn("career-ops", text)


class OutputWriterCase(unittest.TestCase):
    def test_main_in_process_writes_the_summary_to_stdout_only(self):
        old = (sys.stdout, sys.stderr)
        try:
            sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
            code = cli.main(["wrapped-compounds", "-h"], environ={})
            got = (code, sys.stdout.getvalue(), sys.stderr.getvalue())
        finally:
            sys.stdout, sys.stderr = old
        self.assertEqual(got, (0, spec_synopsis(), ""))


if __name__ == "__main__":
    unittest.main()
