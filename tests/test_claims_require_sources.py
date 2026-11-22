"""Tests for ``track-record claims --require-local-sources`` and the `no source` lines. All data here is invented.

Revision 3 of the claims spec adds one option and one report. ``--require-local-sources`` runs
every check of ``--check-sources`` and also fails an approved quote it could not check
(unverified) and an approved entry with no source. Under either option every approved or
proposed entry with no source gets a line naming its number and its line in the list, and the
run ends with two `sources` count lines. A proposed entry never changes the exit status, and a
refused entry is never reported. Every list, quote, source and sentence below is made up
(Example Corp., Dana Example, example.com). Lists, inputs and sources are written into a
temporary folder at run time; no fixture file is used. Every run goes through the real command
line in a subprocess, and every assertion checks the exit code, standard output and standard
error whole. Known answers 9.20 to 9.31 are reused from tests.test_claims_sources, where they
already hold the revision 3 output.
"""

import unittest

from tests.test_claims import CASES, HELP, SIX, fail, finding, ok
from tests.test_claims_sources import (
    ENTRY_3, KNOWN, L2, L2_NAME, SECRETS, SourcesCase, counts, line, no_source,
)

# Three approved entries for the exit-2 test. Their sentences differ from each other and from
# every sentence of L2, because the command refuses a list that repeats a sentence.
UNREADABLE_ENTRY = "approved\tStarted at Example Corp. in 2019.\tevidence\nquote\tjoined the team\n"
UNVERIFIED_ENTRY = ("approved\tMoved to the Example platform group in 2020.\t"
                    "https://example.com/records/1\nquote\tjoined the team\n")
NO_SOURCE_ENTRY = "approved\tClosed the Example audit backlog in 2022.\n"

REQUIRE = "--require-local-sources"
CHECK = "--check-sources"
MENTORED = "proposed\tMentored two interns.\n"
LIST_SECRETS = SECRETS + ("offer-letter", "notes/", "start.txt", "invented note", "draft.txt",
                          "Mentored", "interns", "Increased revenue")


class RequireCase(SourcesCase):
    def run_with(self, list_text, flags, text=SIX, control="example", extra=()):
        """Write the list and f.txt, run the gate with `flags`; (code, out, err)."""
        self.put(L2_NAME, list_text)
        self.put("f.txt", text)
        args = ["--list", L2_NAME, "--control", control] + list(extra) + list(flags) + ["f.txt"]
        return self.claims(args)

    def known_with(self, key, flags, code=None):
        """A known answer of tests.test_claims_sources, run with other flags; (got, expected)."""
        list_text, text, control, extra, out, expected = KNOWN[key]
        got = self.run_with(list_text, flags, text, control, extra)
        return got, (expected if code is None else code, out, "")


class KnownAnswers(RequireCase):
    def test_9_37_an_approved_unverified_quote_exits_1(self):
        got, expected = self.known_with(23, [REQUIRE], 1)
        self.assertEqual(got, expected)
        self.assertEqual(expected[1].count("approved, entry #5: source unverified\n"), 1)

    def test_9_38_check_sources_as_well_or_the_option_twice_changes_nothing(self):
        for flags in ([REQUIRE, CHECK], [CHECK, REQUIRE], [REQUIRE, REQUIRE]):
            with self.subTest(flags=flags):
                got, expected = self.known_with(23, flags, 1)
                self.assertEqual(got, expected)

    def test_9_39_proposed_entries_never_change_the_exit(self):
        got, expected = self.known_with(24, [REQUIRE], 0)
        self.assertEqual(got, expected)
        self.assertIn(line("proposed", 5, "source unreadable (not a regular file)"), expected[1])
        self.assertIn(line("proposed", 6, "source unverified"), expected[1])

    def test_9_40_an_approved_entry_with_no_source_exits_1_and_a_refused_one_is_not_reported(self):
        got, expected = self.known_with(31, [REQUIRE], 1)
        self.assertEqual(got, expected)
        # L1's refused entry #6 has no source and appears nowhere; proposed #5 has one.
        self.assertNotIn("entry #6", expected[1])
        self.assertNotIn("entry #5", expected[1])
        # The same run under --check-sources alone keeps its exit status of 0.
        got, expected = self.known_with(31, [CHECK], 0)
        self.assertEqual(got, expected)

    def test_9_41_every_approved_quote_found_and_every_approved_entry_sourced_exits_0(self):
        got, expected = self.known_with(20, [REQUIRE], 0)
        self.assertEqual(got, expected)

    def test_9_42_a_value_is_an_unknown_option_and_help_wins(self):
        self.put("f.txt", SIX)
        self.put(L2_NAME, L2)
        self.assertEqual(
            self.claims(["--list", L2_NAME, "--control", "example", REQUIRE + "=1", "f.txt"]),
            (2, "", "cannot run: unknown option --require-local-sources=1\n"))
        for args in (["--help", REQUIRE], [REQUIRE, "-h"],
                     ["--list", L2_NAME, REQUIRE, "--help", "f.txt"]):
            with self.subTest(args=args):
                self.assertEqual(self.claims(args), (0, HELP, ""))

    def test_the_strict_option_is_never_the_value_of_list_or_control(self):
        self.put("f.txt", SIX)
        self.put(L2_NAME, L2)
        cases = (
            (["--list", L2_NAME, "--control", REQUIRE, "f.txt"],
             (2, "", "cannot run: --control needs a value\n")),
            (["--list", REQUIRE, "--control", "example", "f.txt"],
             (2, "", "cannot run: --list needs a value\n")),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(self.claims(args), expected)

    def test_9_43_neither_option_prints_what_revision_2_printed(self):
        for number in range(1, 14):
            text, control, extra, out, code = CASES[number]
            with self.subTest(case=number):
                self.assertEqual(self.gate(text, control=control, extra=extra), (code, out, ""))
        self.assertEqual(self.gate(CASES[1][0], control="zebra"),
                         (2, "DEAD  f.txt: control not found\n", ""))
        self.assertEqual(self.gate("- * -\n\n- * -\n", control="-"),
                         (2, "DEAD  f.txt: no checked sentence\n", ""))
        # L1 has approved entries with no source; without an option nothing says so.
        out = self.gate(SIX)[1]
        self.assertNotIn("no source", out)
        self.assertNotIn("sources, ", out)

    def test_9_44_a_proposed_entry_with_no_source_is_reported_and_counted_and_exits_0(self):
        expected_out = (ok("f.txt", 1) + ENTRY_3 + no_source("proposed", 5, 9)
                        + counts((1, 0, 0, 0), (0, 1, 0, 0), (0, 1)))
        self.assertTrue(expected_out.endswith("sources, proposed: 1 no source\n"))
        for flags in ([REQUIRE], [CHECK]):
            with self.subTest(flags=flags):
                self.assertEqual(self.run_with(L2 + MENTORED, flags), (0, expected_out, ""))

    def test_exit_precedence_is_unchanged_under_the_option(self):
        for key, code in ((21, 1), (22, 2)):
            with self.subTest(case=key):
                got, expected = self.known_with(key, [REQUIRE], code)
                self.assertEqual(got, expected)

    def test_the_option_alone_runs_the_source_check(self):
        """It implies --check-sources: the quote line and counts are there without it."""
        got, expected = self.known_with(21, [REQUIRE])
        self.assertIn(line("approved", 5, "quote not found"), got[1])
        self.assertEqual(got, expected)

    def test_a_dead_input_does_not_stop_the_no_source_lines(self):
        got = self.run_with(L2 + MENTORED, [REQUIRE], control="zebra")
        self.assertEqual(got, (2, "DEAD  f.txt: control not found\n" + ENTRY_3
                               + no_source("proposed", 5, 9)
                               + counts((1, 0, 0, 0), (0, 1, 0, 0), (0, 1)), ""))

    def test_no_source_lines_come_after_every_quote_line_and_before_the_counts(self):
        list_text = ("approved\t%s\n" % SIX
                     + "proposed\tCut build times by forty percent.\n"
                     + "approved\tShipped the Example importer in 2021.\thttps://example.com/1\n"
                     + "quote\tshipped it\n"
                     + "proposed\tBuilt an end-to-end import pipeline.\tevidence/offer.txt\n"
                     + "quote\tnot in the source\n")
        want = (ok("f.txt", 1)
                + line("approved", 3, "source unverified")
                + line("proposed", 4, "quote not found")
                + no_source("approved", 1, 1) + no_source("proposed", 2, 2)
                + counts((0, 0, 0, 1), (0, 1, 0, 0), (1, 1)))
        self.assertEqual(self.run_with(list_text, [REQUIRE]), (1, want, ""))
        self.assertEqual(self.run_with(list_text, [CHECK]), (0, want, ""))

    def test_a_stale_line_comes_before_the_quote_and_no_source_lines(self):
        got = self.run_with(L2 + MENTORED, [REQUIRE], extra=["--stale-check"])
        self.assertEqual(got, (1, ok("f.txt", 1) + "stale entry #2\n" + ENTRY_3
                               + no_source("proposed", 5, 9)
                               + counts((1, 0, 0, 0), (0, 1, 0, 0), (0, 1)), ""))

    def test_an_unreadable_source_keeps_exit_2_when_another_approved_entry_would_exit_1(self):
        """The unreadable entry comes first: a later entry may raise the exit only to 1."""
        unreadable = line("approved", 5, "source unreadable (not a regular file)")
        for name, tail, found, want in (
                ("unverified", UNVERIFIED_ENTRY,
                 (1, 0, 1, 1), unreadable + line("approved", 6, "source unverified")),
                ("no source", NO_SOURCE_ENTRY,
                 (1, 0, 1, 0), unreadable)):
            with self.subTest(second=name):
                missing = (1, 0) if name == "no source" else (0, 0)
                out = (ok("f.txt", 1) + ENTRY_3 + want
                       + (no_source("approved", 6, 11) if name == "no source" else "")
                       + counts(found, (0, 1, 0, 0), missing))
                self.assertEqual(self.run_with(L2 + UNREADABLE_ENTRY + tail, [REQUIRE]),
                                 (2, out, ""))

    def test_a_failing_input_still_exits_1_when_every_source_is_fine(self):
        got = self.run_with(L2, [REQUIRE], text="Led a team of seven engineers at Example Corp.")
        self.assertEqual(got, (1, fail("f.txt", 1, 1)
                               + finding("f.txt", 1, "unlisted",
                                         "Led a team of seven engineers at Example Corp.")
                               + ENTRY_3 + counts((1, 0, 0, 0), (0, 1, 0, 0)), ""))


class ListLines(RequireCase):
    """The reported list line is the 1-based physical line of the list file."""

    def test_a_bom_crlf_blank_and_comment_lines_before_the_entry(self):
        list_text = (chr(0xFEFF) + "# invented comment\r\n\r\n# another\r\n   \r\n"
                     "approved\t%s\r\n" % SIX)
        want = ok("f.txt", 1) + no_source("approved", 1, 5) + counts(unsourced=(1, 0))
        self.assertEqual(self.run_with(list_text, [REQUIRE]), (1, want, ""))
        self.assertEqual(self.run_with(list_text, [CHECK]), (0, want, ""))

    def test_quote_lines_and_a_lone_carriage_return_count_as_lines(self):
        list_text = ("# c\n"
                     "approved\t%s\tevidence/offer.txt\n" % SIX
                     + "quote\twill lead a group of six engineers\r"
                     + "\r\n"
                     + "proposed\tMentored two interns.\n"
                     + "refused\tIncreased revenue tenfold.\n"
                     + "approved\tShipped the Example importer in 2021.\n")
        want = (ok("f.txt", 1) + no_source("proposed", 2, 5) + no_source("approved", 4, 7)
                + counts((1, 0, 0, 0), unsourced=(1, 1)))
        self.assertEqual(self.run_with(list_text, [REQUIRE]), (1, want, ""))


class Privacy(RequireCase):
    def test_9_33_no_quote_source_note_path_or_sentence_reaches_any_output(self):
        outputs = [self.run_with(L2 + MENTORED, [flag]) for flag in (REQUIRE, CHECK)]
        for key, flags in ((23, [REQUIRE]), (23, [REQUIRE, CHECK]), (23, [REQUIRE, REQUIRE]),
                           (24, [REQUIRE]), (31, [REQUIRE]), (20, [REQUIRE])):
            outputs.append(self.known_with(key, flags)[0])
        outputs.append(self.claims([REQUIRE + "=1", "f.txt"]))
        outputs.append(self.claims([REQUIRE, "--help"]))
        outputs.append(self.run_with(L2 + MENTORED, [REQUIRE], control="zebra"))
        secrets = LIST_SECRETS + (self.dir, self._tmp.name)
        self.assertEqual(len(outputs), 11)
        for code, out, err in outputs:
            for secret in secrets:
                self.assertNotIn(secret, out)
                self.assertNotIn(secret, err)


if __name__ == "__main__":
    unittest.main()
