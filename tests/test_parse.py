"""Tests for ``track-record parse`` that need no real PDF (spec: docs/specs/parse.md, section 7).

Text cases T1 to T19 call the pure function ``check_text`` with literal texts (D is the default
text, L the layout text, ``\\f`` a form feed). Cases U1 to U5 run the command line in process
or in a child process on arguments, text files and a stand-in ``pdftotext``. The PDF cases
P1 to P9 are in tests/test_parse_pdf.py. Expected strings are written out here, never computed
by the code under test. All data here is invented. No raw invisible character appears in this
file; special characters are built with chr().
"""

import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
MODULE = os.path.join(SRC, "career_track_record", "parse.py")
sys.path.insert(0, SRC)

from career_track_record import cli, parse  # noqa: E402

LIGATURE_FI = chr(0xFB01)
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
REPLACEMENT = chr(0xFFFD)
E_DIAERESIS = chr(0xEB)
DIAERESIS = chr(0x308)
ESC = chr(0x1B)
ZERO_WIDTH_SPACE = chr(0x200B)

TAIL = ("; fix them in the document the PDF was made from, make the PDF again, and run "
        "this again")
NO_TEXT = "no text; the PDF holds no selectable text (a scan?), so export it again from the document"
NO_OUTPUT = "cannot run: cannot write output\n"

# The usage block of spec 1, section 2, byte for byte.
HELP = """\
usage: track-record parse --name TEXT [--contact TEXT]... [--sections LIST]
                          [--min-page-chars N] FILE...

Shows what a program that reads a PDF's text gets from your résumé: whether
there is text on every page, whether your name and contact details are on
page 1, which common English section headings (such as Experience or Skills)
it can see, how many date formats your date ranges use, and whether a
hyphenated word is split across two lines.

It cannot tell what any particular hiring system will accept. A file can
pass here and still be misread by one.

  --name TEXT          your name as it appears in the PDF (required); if it is
                       not found the file is reported DEAD (it could not be
                       checked)
  --contact TEXT       an email, phone number or link, written as it appears
                       in the PDF, that should be on page 1; repeatable
  --sections LIST      section families that must appear, separated by commas
                       (default: experience,skills); families: experience,
                       education, skills, summary, projects, certifications
  --min-page-chars N   a page with fewer letters or digits than this is
                       reported as having little or no text (default 20)
  -h, --help           show this summary and exit

exit: 0 no finding, 1 a finding, 2 no verdict (a file is DEAD, or the command
      could not run); 2 is not a pass
"""

BASE = "Ada Example\nExperience\nSkills\n"
BASE_BLOCK = [
    "OK    x.pdf",
    "  text: 1 page, 1 with text",
    "  name: page 1",
    "  sections: experience found (page 1 line 2: Experience), "
    "skills found (page 1 line 3: Skills)",
    "  dates: no date ranges found",
    "  wrapped compounds: none",
]
DEFAULT_SECTIONS = ["experience", "skills"]


def check(default, layout=None, name="Ada Example", contacts=(), sections=(),
          min_page_chars=1):
    """check_text as the text cases call it. ``sections`` defaults to none required, so a
    case about something else is not failed by a heading it never wrote."""
    return parse.check_text(default, default if layout is None else layout, name,
                            list(contacts), list(sections), min_page_chars, "x.pdf")


def fail_line(count):
    return "FAIL  x.pdf: %d finding%s%s" % (count, "" if count == 1 else "s", TAIL)


def with_name(text):
    return "Ada Example\n" + text


class TextCases(unittest.TestCase):
    def test_T1_a_name_split_by_a_line_break_is_found(self):
        status, lines = check("Ada\nExample\nExperience\nSkills\n", sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "OK")
        self.assertIn("  name: page 1", lines)

    def test_T2_a_ligature_in_the_text_matches_the_plain_letters(self):
        text = with_name("Mail " + LIGATURE_FI + "nd@example.com\n")
        status, lines = check(text, contacts=["find@example.com"])
        self.assertEqual(status, "OK")
        self.assertIn('  contact "find@example.com": page 1', lines)

    def test_T3_nfkc_makes_composed_and_decomposed_letters_match(self):
        composed = "Zo" + E_DIAERESIS + " Example"
        decomposed = "Zoe" + DIAERESIS + " Example"
        for text, name in ((composed, composed), (decomposed, composed),
                           (composed, decomposed)):
            with self.subTest(text=text, name=name):
                status, lines = check(text + "\n", name=name)
                self.assertIn("  name: page 1", lines)
                self.assertEqual(status, "OK")

    def test_T4_a_one_word_name_is_found_inside_an_email_address(self):
        status, lines = check("ada@example.com\n", name="Example")
        self.assertEqual(status, "OK")
        self.assertIn("  name: page 1", lines)
        # The boundary rule: a name inside a longer word is not found.
        status, lines = check("ada@examples.com\n", name="Example")
        self.assertEqual(status, "DEAD")
        self.assertEqual(lines[0], "DEAD  x.pdf: name not found; check that the name you "
                                   "gave matches the PDF, and that its text can be selected")

    def test_T5_contacts_on_page_one_later_or_nowhere(self):
        text = BASE + "\fada@example.com\n"
        status, lines = check(text, contacts=["ada@example.com", "nobody@example.com"],
                              sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(2))
        self.assertIn('  contact "ada@example.com": found on page 2, not page 1', lines)
        self.assertIn('  contact "nobody@example.com": not found', lines)
        self.assertEqual(lines.index('  contact "ada@example.com": found on page 2, not '
                                     'page 1') + 1,
                         lines.index('  contact "nobody@example.com": not found'))
        status, lines = check(BASE, sections=DEFAULT_SECTIONS)
        self.assertEqual((status, lines), ("OK", BASE_BLOCK))
        self.assertEqual([line for line in lines if line.startswith("  contact")], [])

    def test_T6_a_heading_no_reader_would_take_is_missing_and_not_reported(self):
        status, lines = check("Ada Example\nExperience\nWhat I use\n",
                              sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertIn("  sections: experience found (page 1 line 2: Experience), "
                      "skills missing", lines)
        self.assertFalse([line for line in lines if "What I use" in line])

    def test_T7_a_heading_with_a_colon_counts_and_a_longer_line_does_not(self):
        status, lines = check("Ada Example\nWork Experience:\nSkills\n",
                              sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "OK")
        self.assertIn("  sections: experience found (page 1 line 2: Work Experience:), "
                      "skills found (page 1 line 3: Skills)", lines)
        status, lines = check("Ada Example\nExperience at a glance\nSkills\n",
                              sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "FAIL")
        self.assertIn("  sections: experience missing, skills found (page 1 line 3: Skills)",
                      lines)

    def test_T8_a_required_family_that_is_absent_is_a_finding_by_choice_of_sections(self):
        three = ["experience", "education", "skills"]
        status, lines = check(BASE, sections=three)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertIn("  sections: experience found (page 1 line 2: Experience), "
                      "education missing, skills found (page 1 line 3: Skills)", lines)
        status, lines = check(BASE, sections=DEFAULT_SECTIONS)
        self.assertEqual((status, lines), ("OK", BASE_BLOCK))

    def test_T9_a_found_family_that_is_not_required_comes_after_the_required_ones(self):
        status, lines = check(BASE + "Projects\n", sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "OK")
        self.assertIn("  sections: experience found (page 1 line 2: Experience), skills "
                      "found (page 1 line 3: Skills), projects found (page 1 line 4: "
                      "Projects)", lines)

    def test_T10_three_formats_in_three_ranges_are_a_finding(self):
        text = with_name("Jan 2020 " + EN_DASH + " Present\n2017 - 2019\n03/2014 to 02/2017\n")
        status, lines = check(text)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertIn("  dates: 3 formats (MM/YYYY 2, YYYY 2, Mon YYYY 1)", lines)

    def test_two_formats_in_two_ranges_are_a_finding(self):
        text = with_name("Jan 2020 " + EN_DASH + " Present\n2017 - 2019\n")
        status, lines = check(text)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertIn("  dates: 2 formats (YYYY 2, Mon YYYY 1)", lines)

    def test_T11_running_text_is_not_a_range_and_a_year_range_is_two_years(self):
        status, lines = check(with_name("since 2015\n"))
        self.assertIn("  dates: no date ranges found", lines)
        status, lines = check(with_name("2017-2019\n"))
        self.assertEqual(status, "OK")
        self.assertIn("  dates: 1 format (YYYY 2)", lines)

    def test_T12_an_em_dash_and_the_year_month_form(self):
        status, lines = check(with_name("Sept. 2019 " + EM_DASH + " May 2021\n"))
        self.assertIn("  dates: 1 format (Mon YYYY 2)", lines)
        status, lines = check(with_name("2019-03 to 2021-11\n"))
        self.assertIn("  dates: 1 format (YYYY-MM 2)", lines)

    def test_T13_a_day_first_date_counts_nothing_and_the_month_first_form_counts_two(self):
        status, lines = check(with_name("13/02/2019 - 14/03/2020\n"))
        self.assertIn("  dates: no date ranges found", lines)
        status, lines = check(with_name("03/02/2019 - 04/05/2020\n"))
        self.assertIn("  dates: 1 format (MM/DD/YYYY 2)", lines)

    def test_T14_a_range_split_across_two_lines_counts_nothing(self):
        status, lines = check(with_name("Jan 2020 -\nPresent\n"))
        self.assertIn("  dates: no date ranges found", lines)
        self.assertEqual(status, "OK")

    def test_T15_no_range_is_not_a_finding(self):
        status, lines = check(BASE, sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "OK")
        self.assertIn("  dates: no date ranges found", lines)

    def test_T16_one_trailing_form_feed_does_not_make_a_third_page(self):
        status, lines = check(BASE + "\fSecond page text.\f")
        self.assertIn("  text: 2 pages, 2 with text", lines)

    def test_T17_a_page_below_the_threshold_is_a_finding_and_not_dead(self):
        text = "Ada Example\nSkills\nabc\n"
        status, lines = check(text, sections=["skills"], min_page_chars=20)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertEqual(lines[1], "  text: 1 page, 0 with text")
        self.assertEqual(lines[2], "  page 1: little or no text (19 letters or digits)")
        status, lines = check(text, sections=["skills"], min_page_chars=19)
        self.assertEqual(status, "OK")
        self.assertEqual(lines[1], "  text: 1 page, 1 with text")
        self.assertEqual(lines, ["OK    x.pdf", "  text: 1 page, 1 with text",
                                 "  name: page 1",
                                 "  sections: skills found (page 1 line 2: Skills)",
                                 "  dates: no date ranges found",
                                 "  wrapped compounds: none"])
        # U+FFFD counts as neither a letter nor a digit.
        status, lines = check("Ada Example\n\f" + REPLACEMENT * 5 + "\n")
        self.assertEqual(status, "FAIL")
        self.assertIn("  page 2: little or no text (0 letters or digits)", lines)
        status, lines = check(REPLACEMENT * 5 + "\n")
        self.assertEqual(status, "DEAD")
        self.assertEqual(lines, ["DEAD  x.pdf: " + NO_TEXT, "  text: 1 page, 0 with text",
                                 "  page 1: little or no text (0 letters or digits)"])

    def test_T18_a_wrapped_compound_is_a_finding_and_a_note_is_not(self):
        layout = "Ada Example\nThe well-\nknown results held.\n"
        default = "Ada Example\nThe wellknown results held.\n"
        status, lines = check(default, layout)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertIn('  wrapped compounds: page 1 line 2: "well-known" is split across '
                      'lines; extracted text reads "wellknown" (finding)', lines)
        self.assertFalse([line for line in lines if line.startswith("  next:")])
        layout = "Ada Example\nmanage-\nment\fAda Example\nmanagement\f"
        default = "Ada Example\nmanagement\fAda Example\nmanagement\f"
        status, lines = check(default, layout)
        self.assertEqual(status, "OK")
        self.assertEqual(lines[0], "OK    x.pdf")
        self.assertIn('  wrapped compounds: page 1 line 2: "manage-ment" is split across '
                      'lines; extracted text reads "management" (note: "management" also '
                      'appears unwrapped, nothing to fix)', lines)

    def test_T19_different_page_counts_are_dead_after_the_text_line(self):
        status, lines = check("Ada Example\nExperience\n",
                              "Ada Example\nExperience\fAda Example\n")
        self.assertEqual(status, "DEAD")
        self.assertEqual(lines, ["DEAD  x.pdf: page counts differ (default 1, layout 2); "
                                 "export the PDF again", "  text: 1 page, 1 with text"])


class ReturnShapeCases(unittest.TestCase):
    def test_the_status_line_is_first_and_the_path_is_escaped(self):
        status, lines = parse.check_text(BASE, BASE, "Ada Example", [], DEFAULT_SECTIONS, 1,
                                         "a\nb.pdf")
        self.assertEqual((status, lines[0]), ("OK", "OK    a\\nb.pdf"))
        status, lines = parse.check_text(BASE, BASE, "Ada Example", [], DEFAULT_SECTIONS, 1)
        self.assertEqual(lines[0], "OK    x.pdf")

    def test_the_second_page_name_is_a_finding(self):
        status, lines = check("Experience\nSkills\f" + BASE, sections=DEFAULT_SECTIONS)
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertIn("  name: found on page 2, not page 1", lines)

    def test_the_name_is_looked_for_page_by_page_never_across_a_page_break(self):
        status, lines = check("Ada\fExample\n")
        self.assertEqual(status, "DEAD")

    def test_a_later_occurrence_with_a_boundary_is_found_after_an_earlier_one_without(self):
        status, lines = check("examples ada@example.com\n", name="Example")
        self.assertEqual(status, "OK")
        self.assertIn("  name: page 1", lines)

    def test_two_findings_are_plural(self):
        status, lines = check("Ada Example\n", sections=DEFAULT_SECTIONS)
        self.assertEqual(lines[0], fail_line(2))

    def test_a_date_range_boundaries(self):
        for text in ("Presentation 2019 - Presentation", "Jan 2020 - Presentation",
                     "Jan 2020 - Currently"):
            with self.subTest(text=text):
                status, lines = check(with_name(text + "\n"))
                self.assertIn("  dates: no date ranges found", lines)
        status, lines = check(with_name("Jan 2020 - current\n"))
        self.assertIn("  dates: 1 format (Mon YYYY 1)", lines)
        status, lines = check(with_name("2019 to 2021\n"))
        self.assertIn("  dates: 1 format (YYYY 2)", lines)
        status, lines = check(with_name("2019to 2021\n"))
        self.assertIn("  dates: no date ranges found", lines)

    def test_a_year_month_range_beside_a_longer_number_is_not_a_date(self):
        status, lines = check(with_name("2019-031 - 2021\n"))
        self.assertIn("  dates: no date ranges found", lines)

    def test_a_date_touching_a_letter_a_digit_or_a_slash_is_not_a_date(self):
        for text in ("a2019 - 2020", "2019 - 2020a", "13/02/2019 - 2020", "2019 - 20201",
                     "12019 - 2020"):
            with self.subTest(text=text):
                status, lines = check(with_name(text + "\n"))
                self.assertIn("  dates: no date ranges found", lines)

    def test_a_tab_may_separate_the_month_name_and_the_year(self):
        status, lines = check(with_name("mar\t2017 - dec\t2019\n"))
        self.assertIn("  dates: 1 format (Mon YYYY 2)", lines)

    def test_classes_are_listed_by_count_then_in_class_order(self):
        text = with_name("2017 - 2019\n03/2014 - 02/2017\n2019-03 - 2021-11\n")
        status, lines = check(text)
        self.assertIn("  dates: 3 formats (MM/YYYY 2, YYYY-MM 2, YYYY 2)", lines)

    def test_a_heading_is_the_first_of_its_family_in_page_and_line_order(self):
        status, lines = check("Ada Example\nSkills\nTechnical Skills\fExperience\n",
                              sections=DEFAULT_SECTIONS)
        self.assertIn("  sections: experience found (page 2 line 1: Experience), skills "
                      "found (page 1 line 2: Skills)", lines)

    def test_sections_are_listed_in_the_order_of_the_list_file(self):
        status, lines = check(BASE, sections=["skills", "experience"])
        self.assertIn("  sections: experience found (page 1 line 2: Experience), skills "
                      "found (page 1 line 3: Skills)", lines)


class FixRoundCases(unittest.TestCase):
    """Rules of the signed spec that the first review found no test pinning."""

    def test_the_character_before_a_name_or_contact_must_be_a_boundary(self):
        status, lines = check("ada@counterexample.com\n", name="Example")
        self.assertEqual(status, "DEAD")
        self.assertEqual(lines[0], "DEAD  x.pdf: name not found; check that the name you "
                                   "gave matches the PDF, and that its text can be selected")
        status, lines = check("ada@counterexample.com\n", name="ada", contacts=["example"])
        self.assertEqual(status, "FAIL")
        self.assertEqual(lines[0], fail_line(1))
        self.assertIn('  contact "example": not found', lines)

    def test_lines_are_numbered_from_one_on_each_page_blank_lines_included(self):
        status, lines = check("Ada Example\n\n\nExperience\n", sections=["experience"])
        self.assertIn("  sections: experience found (page 1 line 4: Experience)", lines)

    def test_a_contact_prints_escaped_as_a_printed_path_is(self):
        status, lines = check(BASE, contacts=["a" + ESC + "b"])
        self.assertEqual(status, "FAIL")
        self.assertIn('  contact "a\\x1bb": not found', lines)

    def test_day_31_is_a_day(self):
        status, lines = check(with_name("01/31/2020 - 02/28/2020\n"))
        self.assertIn("  dates: 1 format (MM/DD/YYYY 2)", lines)

    def test_years_in_the_nineteen_hundreds_are_years(self):
        status, lines = check(with_name("Jan 1999 - Dec 2001\n"))
        self.assertIn("  dates: 1 format (Mon YYYY 2)", lines)

    def test_a_tab_may_stand_before_and_after_the_separator(self):
        status, lines = check(with_name("Jan 2020\t-\tPresent\n"))
        self.assertIn("  dates: 1 format (Mon YYYY 1)", lines)
        status, lines = check(with_name("Jan 2020 -\tDec 2021\n"))
        self.assertIn("  dates: 1 format (Mon YYYY 2)", lines)

    def test_the_word_to_needs_a_space_or_tab_after_it(self):
        status, lines = check(with_name("2017 topresent\n"))
        self.assertIn("  dates: no date ranges found", lines)
        status, lines = check(with_name("2017 to\t2019\n"))
        self.assertIn("  dates: 1 format (YYYY 2)", lines)

    def test_min_page_chars_takes_eighteen_significant_digits_and_not_nineteen(self):
        def go(value):
            return parse.run(files=["missing.txt"], name="Ada Example", contacts=[],
                             sections=None, min_page_chars=value)
        for value in ("1" + "0" * 17, "0" * 5 + "1" + "0" * 17):
            with self.subTest(value=value):
                result = go(value)
                self.assertTrue(result.ran)
                self.assertEqual(result.exit_code, 2)
                self.assertEqual(result.text, "DEAD  missing.txt: not a PDF; give the PDF file\n")
        result = go("1" + "0" * 18)
        self.assertFalse(result.ran)
        self.assertEqual(result.error, "cannot run: --min-page-chars takes a whole number "
                                       "of 1 or more")


class UsageCases(unittest.TestCase):
    """U1: the usage errors of section 2, in their order, with no file read."""

    def usage(self, args, message):
        out, err = io.StringIO(), io.StringIO()
        old = (sys.stdout, sys.stderr)
        try:
            sys.stdout, sys.stderr = out, err
            code = cli.main(["parse"] + args, environ={})
        finally:
            sys.stdout, sys.stderr = old
        self.assertEqual((code, out.getvalue(), err.getvalue()),
                         (2, "", "cannot run: " + message + "\n"), args)

    def test_U1_each_usage_error_has_its_line(self):
        families = "families: experience, education, skills, summary, projects, certifications"
        self.usage(["--bogus", "--name", "a", "f.pdf"], "unknown option --bogus")
        self.usage(["--name=a", "f.pdf", "--bad=1"], "unknown option --bad=1")
        self.usage(["--name"], "--name needs a value")
        self.usage(["--name", "--contact", "x", "f.pdf"], "--name needs a value")
        self.usage(["--name", "a", "--name", "b", "f.pdf"], "--name given twice")
        self.usage(["--name", "a", "--sections", "skills", "--sections=skills", "f.pdf"],
                   "--sections given twice")
        self.usage(["--name", "a", "--min-page-chars", "1", "--min-page-chars", "2", "f.pdf"],
                   "--min-page-chars given twice")
        self.usage(["--name", "a"], "no input file")
        self.usage([], "no input file")
        self.usage(["f.pdf"], "give --name, your name as it appears in the PDF")
        self.usage(["--name", "  ", "f.pdf"], "--name is empty")
        self.usage(["--name", "a", "--contact", ZERO_WIDTH_SPACE, "f.pdf"],
                   "--contact is empty")
        self.usage(["--name", "a", "--contact", "ok", "--contact", "", "f.pdf"],
                   "--contact is empty")
        whole = "--min-page-chars takes a whole number of 1 or more"
        for bad in ("0", "00", "abc", "", "-1", "+5", "1.5", "1" + "0" * 18):
            with self.subTest(min_page_chars=bad):
                self.usage(["--name", "a", "--min-page-chars=" + bad, "f.pdf"], whole)
        self.usage(["--name", "a", "--sections", "", "f.pdf"],
                   "--sections: empty family name")
        self.usage(["--name", "a", "--sections", "skills,,summary", "f.pdf"],
                   "--sections: empty family name")
        self.usage(["--name", "a", "--sections", "skills,", "f.pdf"],
                   "--sections: empty family name")
        self.usage(["--name", "a", "--sections", "skills,hobbies", "f.pdf"],
                   "--sections: unknown family hobbies; " + families)
        self.usage(["--name", "a", "--sections", "Skills, HOBBIES ", "f.pdf"],
                   "--sections: unknown family hobbies; " + families)

    def test_errors_1_to_3_first_found_is_the_one_printed(self):
        self.usage(["--name", "a", "--name", "b", "--bogus"], "--name given twice")
        self.usage(["--bogus", "--name"], "unknown option --bogus")
        self.usage(["--name"] + ["--sections"], "--name needs a value")
        self.usage(["--sections", "skills", "--sections", "--name", "a"],
                   "--sections needs a value")

    def test_errors_4_to_9_follow_their_listed_order(self):
        whole = "--min-page-chars takes a whole number of 1 or more"
        self.usage(["--sections", "nope", "--min-page-chars", "0"], "no input file")
        self.usage(["--sections", "nope", "--min-page-chars", "0", "f.pdf"],
                   "give --name, your name as it appears in the PDF")
        self.usage(["--name", " ", "--sections", "nope", "--min-page-chars", "0", "f.pdf"],
                   "--name is empty")
        self.usage(["--name", "a", "--sections", "nope", "--min-page-chars", "0", "f.pdf"],
                   whole)
        families = "families: experience, education, skills, summary, projects, certifications"
        self.usage(["--name", "a", "--sections", "nope", "f.pdf"],
                   "--sections: unknown family nope; " + families)

    def test_a_double_dash_ends_options(self):
        out, err = io.StringIO(), io.StringIO()
        old = (sys.stdout, sys.stderr)
        try:
            sys.stdout, sys.stderr = out, err
            code = cli.main(["parse", "--name", "a", "--", "--missing.pdf"], environ={})
        finally:
            sys.stdout, sys.stderr = old
        self.assertEqual((code, err.getvalue()), (2, ""))
        self.assertEqual(out.getvalue(), "DEAD  --missing.pdf: cannot read\n")

    def test_help_wins_over_every_other_argument(self):
        for args in (["-h"], ["--help"], ["--bogus", "-h"], ["--name"] + ["-h"],
                     ["--name", "-h"], ["--sections", "nope", "x", "--help"],
                     ["--name", "a", "--name", "b", "-h"]):
            with self.subTest(args=args):
                out, err = io.StringIO(), io.StringIO()
                old = (sys.stdout, sys.stderr)
                try:
                    sys.stdout, sys.stderr = out, err
                    code = cli.main(["parse"] + args, environ={})
                finally:
                    sys.stdout, sys.stderr = old
                self.assertEqual((code, out.getvalue(), err.getvalue()), (0, HELP, ""))


def env(extra=None):
    e = dict(os.environ)
    for name in ("BARRED_STRINGS_PATH", "BARRED_STRINGS", "CTR_CONFIG_DIR", "XDG_CONFIG_HOME"):
        e.pop(name, None)
    e["PYTHONPATH"] = SRC
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def run_cli(args, cwd=ROOT, env_extra=None):
    proc = subprocess.run([sys.executable, "-m", "career_track_record", "parse"] + list(args),
                          cwd=cwd, env=env(env_extra), stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


STAND_IN = """#!/bin/sh
# A stand-in pdftotext for the tests: it logs its first argument and prints the text file
# next to it.
here=$(dirname "$0")
printf '%s\\n' "$1" >> "$here/args.log"
/bin/cat "$here/text.txt"
"""


def stand_in(directory, text):
    """A folder holding a stand-in ``pdftotext`` that prints ``text``."""
    os.makedirs(directory)
    script = os.path.join(directory, "pdftotext")
    with open(script, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(STAND_IN)
    os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
    with open(os.path.join(directory, "text.txt"), "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return directory


class FileNameCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = stand_in(os.path.join(self.tmp, "bin"), BASE)
        self.work = os.path.join(self.tmp, "work")
        os.mkdir(self.work)
        self.path = self.bin + ":/bin:/usr/bin"

    def touch(self, name):
        with open(os.path.join(self.work, name), "wb") as handle:
            handle.write(b"%PDF stand-in")

    def test_U2_a_newline_or_an_escape_prints_escaped_and_a_dash_path_gets_a_prefix(self):
        names = ["line\nbreak.pdf", "esc" + ESC + "here.pdf"]
        for name in names:
            self.touch(name)
        code, out, err = run_cli(["--name", "Ada Example"] + names, cwd=self.work,
                                 env_extra={"PATH": self.path})
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("OK    line\\nbreak.pdf\n"))
        self.assertIn("\nOK    esc\\x1bhere.pdf\n", out)
        self.assertNotIn(ESC, out)
        self.dash_prefix_case()

    def dash_prefix_case(self):
        self.touch("-lead.pdf")
        code, out, err = run_cli(["--name", "Ada Example", "--", "-lead.pdf"], cwd=self.work,
                                 env_extra={"PATH": self.path})
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("OK    -lead.pdf\n"))
        with open(os.path.join(self.bin, "args.log"), encoding="utf-8") as handle:
            self.assertEqual(handle.read().split("\n")[-3:], ["./-lead.pdf", "./-lead.pdf", ""])

    def test_U3_the_command_writes_no_file(self):
        self.touch("a.pdf")
        before = sorted((n, os.stat(os.path.join(self.work, n)).st_mtime_ns)
                        for n in os.listdir(self.work))
        run_cli(["--name", "Ada Example", "a.pdf", "missing.pdf"], cwd=self.work,
                env_extra={"PATH": self.path})
        after = sorted((n, os.stat(os.path.join(self.work, n)).st_mtime_ns)
                       for n in os.listdir(self.work))
        self.assertEqual(before, after)
        self.assertEqual(after[0][0], "a.pdf")
        self.assertEqual(len(after), 1)

    def test_a_file_that_does_not_end_in_pdf_is_dead_without_a_read(self):
        self.touch("notes.txt")
        code, out, err = run_cli(["--name", "Ada Example", "notes.txt", "NOTES.PDF"],
                                 cwd=self.work, env_extra={"PATH": self.path})
        self.assertEqual((code, err), (2, ""))
        self.assertTrue(out.startswith("DEAD  notes.txt: not a PDF; give the PDF file\n"))
        self.assertIn("DEAD  NOTES.PDF: cannot read\n", out)

    def test_a_pdf_name_in_capitals_is_read(self):
        self.touch("RESUME.PDF")
        code, out, err = run_cli(["--name", "Ada Example", "--sections", "skills",
                                  "RESUME.PDF"], cwd=self.work, env_extra={"PATH": self.path})
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "OK    RESUME.PDF\n"
                              "  text: 1 page, 1 with text\n"
                              "  name: page 1\n"
                              "  sections: skills found (page 1 line 3: Skills), experience "
                              "found (page 1 line 2: Experience)\n"
                              "  dates: no date ranges found\n"
                              "  wrapped compounds: none\n")


class SectionListCases(unittest.TestCase):
    """U4: a damaged list, swapped in through the module's one seam."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_with_list(self, data):
        path = os.path.join(self.tmp, "section-names.txt")
        if data is not None:
            with open(path, "wb") as handle:
                handle.write(data)
        out, err = io.StringIO(), io.StringIO()
        old = (sys.stdout, sys.stderr)
        try:
            sys.stdout, sys.stderr = out, err
            with mock.patch.object(parse, "_SECTION_LIST", path):
                code = cli.main(["parse", "--name", "Ada", "missing.pdf"], environ={})
        finally:
            sys.stdout, sys.stderr = old
        return code, out.getvalue(), err.getvalue()

    def test_U4_a_damaged_list_is_usage_error_9_before_any_file_is_read(self):
        damaged = "cannot run: the shipped section list is missing or damaged; reinstall\n"
        for label, data in (("no tab", b"experience work experience\n"),
                            ("unknown family", b"hobbies\tgardening\n"),
                            ("empty heading", b"experience\t  \n"),
                            ("no entries", b"# only a comment\n\n"),
                            ("bom", b"\xef\xbb\xbfexperience\texperience\n"),
                            ("not utf-8", b"experience\tcaf\xe9\n"),
                            ("missing", None)):
            with self.subTest(label=label):
                self.assertEqual(self.run_with_list(data), (2, "", damaged))

    def test_a_well_formed_list_with_comments_and_blank_lines_is_used(self):
        data = (b"# a comment\n\nexperience\tExperience\nskills\tSkills\n"
                b"projects\tSide work\n")
        code, out, err = self.run_with_list(data)
        self.assertEqual((code, out, err), (2, "DEAD  missing.pdf: cannot read\n", ""))

    def test_the_shipped_list_loads_and_holds_the_table_entries(self):
        headings = parse.load_headings()
        self.assertEqual(headings["experience"], "experience")
        for line in ("Work Experience", "Licences and Certifications", "About Me",
                     "Skills and Tools", "Academic Background", "Selected Projects"):
            with self.subTest(line=line):
                self.assertIn(line.casefold(), headings)
        self.assertEqual(len(headings), 29)


class OutputCases(unittest.TestCase):
    def test_U5_help_prints_the_summary_and_a_failed_write_exits_2(self):
        code, out, err = run_cli(["-h"])
        self.assertEqual((code, out, err), (0, HELP, ""))
        proc = subprocess.run(
            ["/bin/sh", "-c", 'exec "$0" "$@" >&-', sys.executable, "-m", "career_track_record",
             "parse", "-h"],
            cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr.decode("utf-8")),
                         (2, b"", NO_OUTPUT))

    def test_a_stdout_with_no_reader_exits_2(self):
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "career_track_record", "parse", "-h"], cwd=ROOT,
                env=env(), stdin=subprocess.DEVNULL, stdout=write_end, stderr=subprocess.PIPE)
        finally:
            os.close(write_end)
        self.assertEqual((proc.returncode, proc.stderr.decode("utf-8")), (2, NO_OUTPUT))

    def test_help_in_a_non_utf8_locale_still_prints_the_accent(self):
        code, out, err = run_cli(["-h"], env_extra={"LC_ALL": "C", "PYTHONIOENCODING": "ascii"})
        self.assertEqual((code, out, err), (0, HELP, ""))


class SourceCases(unittest.TestCase):
    def test_parse_py_starts_no_program(self):
        with open(MODULE, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("subprocess", source)


class CliSpecListCase(unittest.TestCase):
    def test_the_cli_spec_lists_the_command_in_the_help_list_once(self):
        with open(os.path.join(ROOT, "docs", "specs", "cli.md"), encoding="utf-8") as handle:
            text = handle.read()
        line = "- parse: check what a text extractor gets from your r\u00e9sum\u00e9 PDF\n"
        self.assertEqual(text.count(line), 1)
        self.assertLess(text.index("- wrapped-compounds: find hyphenated"), text.index(line))
        self.assertLess(text.index(line), text.index("- setup: choose your record folder"))


class GuideCases(unittest.TestCase):
    NEXT = ("next: reword or change the layout so the word does not break at its hyphen, "
            "export the PDF again, and run this again")
    RUNS = (
        ["--name", "Ada Example", "--contact", "ada@example.com"],
        ["--name", "Ada Example", "--contact", "ada@example.com",
         "--contact", "nobody@example.com"],
        ["--name", "Bo Example"],
    )

    def guide(self):
        with open(os.path.join(ROOT, "docs", "guides", "parse.md"), encoding="utf-8") as handle:
            return handle.read()

    def test_the_first_paragraph_says_what_the_command_cannot_tell(self):
        first = self.guide().split("\n\n")[1]
        self.assertIn("what any particular", first)
        self.assertIn("still be misread", first)

    def test_each_pasted_run_appears_once_and_equals_what_check_file_gives(self):
        text = self.guide()
        old = os.getcwd()
        try:
            os.chdir(ROOT)
            for args in self.RUNS:
                with self.subTest(args=args):
                    name, contacts = args[1], [a for i, a in enumerate(args) if args[i - 1] == "--contact"]
                    status, lines = parse.check_file(
                        "examples/good.pdf", name, contacts, list(parse.DEFAULT_SECTIONS),
                        parse.DEFAULT_MIN_PAGE_CHARS)
                    block = "\n".join("    " + line for line in lines) + "\n"
                    self.assertEqual(text.count(block), 1)
        finally:
            os.chdir(old)

    def test_the_known_limits_of_the_spec_are_all_listed(self):
        text = self.guide()
        for phrase in ("header or footer region", "reading order", "English section names only",
                       "must sit on one line", "Day-first dates are misread",
                       "match only as written", "split across a page break",
                       "is a judgment, not a measurement", "Give the full name",
                       "2 is not a pass"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_guide_names_no_private_tooling(self):
        text = self.guide().lower()
        for word in ("career-ops",):
            self.assertNotIn(word, text)

    def test_the_next_sentence_appears_once(self):
        self.assertEqual(self.guide().count(self.NEXT), 1)


class SpecFileCase(unittest.TestCase):
    def test_the_spec_file_names_its_revision_and_carries_the_signed_block(self):
        with open(os.path.join(ROOT, "docs", "specs", "parse.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertRegex(text, re.compile(r"^Revision: 5\. ", re.M))
        self.assertEqual(text.count("<!-- signed spec begins: sha256 "), 1)
        self.assertEqual(text.count("<!-- signed spec ends -->"), 1)


if __name__ == "__main__":
    unittest.main()
