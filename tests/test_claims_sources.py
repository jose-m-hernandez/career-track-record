"""Tests for ``track-record claims --check-sources``, the quote check. All data here is invented.

The quote check is a port of an evidence-check method in which a quote must appear in the
source it cites. Every list, quote, source and sentence below is made up (Example Corp., Dana
Example, example.com). Lists, inputs and sources are written into a temporary folder at run time;
no fixture file is used. PDF cases put a small stand-in ``pdftotext`` alone on PATH. Invisible
characters are written as escapes, never raw. Every run goes through the real command line in a
subprocess, and every assertion checks the exit code, standard output and standard error whole.
"""

import os
import unittest

from tests.test_claims import (  # noqa: F401
    CASES, HELP, L1, LIST_NAME, SYSTEM_PATH, ClaimsCase, fail, finding, ok, stand_in,
)

SIX = "Led a team of six engineers at Example Corp."
SEVEN = "Led a team of seven engineers at Example Corp."
L2_NAME = "the-list-9-20.tsv"

# List L2 of spec section 9 (tab-separated; invented). Its sources sit under the list's folder.
L2 = (
    "# invented list L2\n"
    "approved\tLed a team of six engineers at Example Corp.\tevidence/offer.txt\n"
    "quote\twill lead a group of six engineers\n"
    "approved\tShipped the Example importer in 2021.\tevidence/offer.txt\n"
    "proposed\tCut build times by forty percent.\tevidence/review.txt\n"
    "quote\tcut the build time in half\n"
    "refused\tIncreased revenue tenfold.\tevidence\n"
    "quote\trevenue grew tenfold\n"
)
MARK = "Ref 555-0199"
OFFER = "Dana Example will lead a group of six engineers at Example Corp. %s.\n" % MARK
REVIEW = "Dana Example cut build times by a third. %s.\n" % MARK

JOINED_NOT_FOUND = ("approved\tJoined Example Corp. in 2019.\tevidence/offer.txt\n"
                    "quote\thired forty interns\n")
JOINED_UNREADABLE = "approved\tJoined Example Corp. in 2019.\tevidence\nquote\tjoined the team\n"
JOINED_UNVERIFIED = ("approved\tJoined Example Corp. in 2019.\thttps://example.com/records/1\n"
                     "quote\tjoined the team\n")
PROPOSED_UNREADABLE = "proposed\tJoined Example Corp. in 2019.\tevidence\nquote\tjoined the team\n"
PROPOSED_UNVERIFIED = ("proposed\tBuilt an end-to-end import pipeline.\tREC-0042\n"
                       "quote\tbuilt the pipeline\n")
BUILT_UNREADABLE = ("proposed\tBuilt an end-to-end import pipeline.\tevidence\n"
                    "quote\tbuilt the pipeline\n")
QUOTED_NOTE = " QUOTE \twill lead a group of six engineers\tinvented quote note"

# Everything that must never reach any output (spec 9.33). The resolved paths are added per run.
SECRETS = (
    "will lead a group", "cut the build time", "revenue grew", "hired forty interns",
    "joined the team", "built the pipeline", "evidence", "example.com/records", "REC-0042",
    "lists/", MARK, "555-0199", "Dana Example", "a third", "invented quote note", L2_NAME,
    "missing.txt", "offer", "review", "link.txt", "bad.txt",
)


def line(status, number, what):
    return "%s, entry #%d: %s\n" % (status, number, what)


def counts(approved=(0, 0, 0, 0), proposed=(0, 0, 0, 0)):
    shape = "quotes, %s: %d found, %d not found, %d unreadable, %d unverified\n"
    return shape % (("approved",) + tuple(approved)) + shape % (("proposed",) + tuple(proposed))


ENTRY_3 = line("proposed", 3, "quote not found")

# The known answers of spec section 9 that are one run each, with --check-sources.
# Each row: (list text, input text, control, extra arguments, expected stdout, expected exit).
KNOWN = {
    20: (L2, SIX, "example", [], ok("f.txt", 1) + ENTRY_3 + counts((1, 0, 0, 0), (0, 1, 0, 0)),
         0),
    21: (L2 + JOINED_NOT_FOUND, SIX, "example", [],
         ok("f.txt", 1) + ENTRY_3 + line("approved", 5, "quote not found")
         + counts((1, 1, 0, 0), (0, 1, 0, 0)), 1),
    22: (L2 + JOINED_UNREADABLE, SIX, "example", [],
         ok("f.txt", 1) + ENTRY_3 + line("approved", 5, "source unreadable (cannot read)")
         + counts((1, 0, 1, 0), (0, 1, 0, 0)), 2),
    23: (L2 + JOINED_UNVERIFIED, SIX, "example", [],
         ok("f.txt", 1) + ENTRY_3 + line("approved", 5, "source unverified")
         + counts((1, 0, 0, 1), (0, 1, 0, 0)), 0),
    24: (L2 + PROPOSED_UNREADABLE + PROPOSED_UNVERIFIED, SIX, "example", [],
         ok("f.txt", 1) + ENTRY_3 + line("proposed", 5, "source unreadable (cannot read)")
         + line("proposed", 6, "source unverified") + counts((1, 0, 0, 0), (0, 1, 1, 1)), 0),
    # 25 is the list in a subfolder: see test_9_25.
    "26a": (L2 + JOINED_UNREADABLE, SEVEN, "example", [],
            fail("f.txt", 1, 1) + finding("f.txt", 1, "unlisted", SEVEN) + ENTRY_3
            + line("approved", 5, "source unreadable (cannot read)")
            + counts((1, 0, 1, 0), (0, 1, 0, 0)), 2),
    "26b": (L2 + JOINED_NOT_FOUND, SIX, "zebra", [],
            "DEAD  f.txt: control not found\n" + ENTRY_3 + line("approved", 5, "quote not found")
            + counts((1, 1, 0, 0), (0, 1, 0, 0)), 2),
    "26c": (L2 + JOINED_NOT_FOUND + BUILT_UNREADABLE, SIX, "example", [],
            ok("f.txt", 1) + ENTRY_3 + line("approved", 5, "quote not found")
            + line("proposed", 6, "source unreadable (cannot read)")
            + counts((1, 1, 0, 0), (0, 1, 1, 0)), 1),
    "27a": (L2 + JOINED_NOT_FOUND, SIX, "example", ["--stale-check"],
            ok("f.txt", 1) + "stale entry #2\nstale entry #5\n" + ENTRY_3
            + line("approved", 5, "quote not found") + counts((1, 1, 0, 0), (0, 1, 0, 0)), 1),
    "27b": (L2 + JOINED_NOT_FOUND, SIX, "zebra", ["--stale-check"],
            "DEAD  f.txt: control not found\n" + ENTRY_3 + line("approved", 5, "quote not found")
            + counts((1, 1, 0, 0), (0, 1, 0, 0)), 2),
    29: (L2, SIX + " Cut build times by forty percent.", "example", [],
         fail("f.txt", 1, 2) + finding("f.txt", 1, "proposed, entry #3",
                                       "Cut build times by forty percent.")
         + ENTRY_3 + counts((1, 0, 0, 0), (0, 1, 0, 0)), 1),
    30: (L2.replace("quote\twill lead a group of six engineers\n", QUOTED_NOTE + "\n"), SIX,
         "example", [], ok("f.txt", 1) + ENTRY_3 + counts((1, 0, 0, 0), (0, 1, 0, 0)), 0),
    31: (L1, SIX + " Shipped the Example importer in 2021.", "example", [],
         ok("f.txt", 2) + counts(), 0),
}

# The list errors of spec 9.28: (list text, stderr). Each is the same with and without the flag.
LIST_ERRORS = (
    ("quote\twill lead a group\n" + L2,
     "cannot run: a quote line comes before the first entry\n"),
    (L2 + "quote\ta second quote\n", "cannot run: entry #4 has two quote lines\n"),
    (L2 + "approved\tJoined Example Corp. in 2019.\nquote\tjoined the team\n",
     "cannot run: entry #5 has a quote but no source\n"),
    (L2 + "approved\tJoined Example Corp. in 2019.\t \t\nquote\tjoined the team\n",
     "cannot run: entry #5 has a quote but no source\n"),
    (L2 + "approved\tJoined Example Corp. in 2019.\tevidence/offer.txt\nquote\n",
     "cannot run: entry #5 has an empty quote\n"),
    (L2 + "approved\tJoined Example Corp. in 2019.\tevidence/offer.txt\nquote\t\n",
     "cannot run: entry #5 has an empty quote\n"),
    (L2 + "approved\tJoined Example Corp. in 2019.\tevidence/offer.txt\nquote\t...\n",
     "cannot run: entry #5 has an empty quote\n"),
    (L2 + "approved\tJoined Example Corp. in 2019.\tevidence/offer.txt\nquote\t\u200b\n",
     "cannot run: entry #5 has an empty quote\n"),
)


def first_source(source):
    """L2 with entry #1's source replaced."""
    return L2.replace("\tevidence/offer.txt\n", "\t%s\n" % source, 1)


PDF_STAND_IN = "printf '%s\\n' 'Dana Example will lead a group of six engineers.'\n"

# Other whole runs with the flag: (list text, pdftotext stand-in body or None, PATH is the
# stand-in folder alone, expected stdout, expected exit). The input is SIX, control "example".
VARIANTS = {
    "not UTF-8": (first_source("evidence/bad.txt"), None, False,
                  ok("f.txt", 1) + line("approved", 1, "source unreadable (not UTF-8)")
                  + ENTRY_3 + counts((0, 0, 1, 0), (0, 1, 0, 0)), 2),
    "directory": (first_source("evidence"), None, False,
                  ok("f.txt", 1) + line("approved", 1, "source unreadable (cannot read)")
                  + ENTRY_3 + counts((0, 0, 1, 0), (0, 1, 0, 0)), 2),
    "dangling link": (first_source("evidence/link.txt"), None, False,
                      ok("f.txt", 1) + line("approved", 1, "source unreadable (cannot read)")
                      + ENTRY_3 + counts((0, 0, 1, 0), (0, 1, 0, 0)), 2),
    "pdftotext missing": (first_source("evidence/offer.pdf"), None, True,
                          ok("f.txt", 1)
                          + line("approved", 1, "source unreadable (pdftotext not found)")
                          + ENTRY_3 + counts((0, 0, 1, 0), (0, 1, 0, 0)), 2),
    "pdftotext fails": (first_source("evidence/offer.pdf"), "exit 1\n", True,
                        ok("f.txt", 1)
                        + line("approved", 1, "source unreadable (pdftotext failed)")
                        + ENTRY_3 + counts((0, 0, 1, 0), (0, 1, 0, 0)), 2),
    "pdf found": (first_source("evidence/offer.pdf"), PDF_STAND_IN, True,
                  ok("f.txt", 1) + ENTRY_3 + counts((1, 0, 0, 0), (0, 1, 0, 0)), 0),
    "pdf not found": (first_source("evidence/offer.pdf"), "printf 'Dana Example left.\\n'\n",
                      True, ok("f.txt", 1) + line("approved", 1, "quote not found")
                      + ENTRY_3 + counts((0, 1, 0, 0), (0, 1, 0, 0)), 1),
    "url": (first_source("https://example.com/records/1"), None, False,
            ok("f.txt", 1) + line("approved", 1, "source unverified")
            + ENTRY_3 + counts((0, 0, 0, 1), (0, 1, 0, 0)), 0),
    "record id": (first_source("REC-0042"), None, False,
                  ok("f.txt", 1) + line("approved", 1, "source unverified")
                  + ENTRY_3 + counts((0, 0, 0, 1), (0, 1, 0, 0)), 0),
    "missing path": (first_source("evidence/missing.txt"), None, False,
                     ok("f.txt", 1) + line("approved", 1, "source unverified")
                     + ENTRY_3 + counts((0, 0, 0, 1), (0, 1, 0, 0)), 0),
    "proposed not found only": (
        "approved\t%s\nproposed\tCut build times by forty percent.\tevidence/review.txt\n"
        "quote\tcut the build time in half\n" % SIX, None, False,
        ok("f.txt", 1) + line("proposed", 2, "quote not found")
        + counts((0, 0, 0, 0), (0, 1, 0, 0)), 0),
    "refused unreadable only": (
        "approved\t%s\nrefused\tIncreased revenue tenfold.\tevidence\n"
        "quote\trevenue grew tenfold\n" % SIX, None, False, ok("f.txt", 1) + counts(), 0),
    "source and no quote": (
        "approved\t%s\tevidence/offer.txt\nproposed\tCut build times by forty percent.\t"
        "evidence/review.txt\n" % SIX, None, False, ok("f.txt", 1) + counts(), 0),
    "blank and comment lines before the quote": (
        "approved\t%s\tevidence/offer.txt\n\n# an invented comment\n\n"
        "quote\twill lead a group of six engineers\n" % SIX, None, False,
        ok("f.txt", 1) + counts((1, 0, 0, 0)), 0),
}

# L1 with a quote line under each entry that names a source; for the flag-off identity (9.34).
L1_QUOTED = (L1.replace("notes/offer-letter.txt\n", "notes/offer-letter.txt\nquote\tled a group\n")
             .replace("invented note\n", "invented note\nquote\tjoined the team\t a note\n")
             .replace("notes/draft.txt\n", "notes/draft.txt\nQUOTE\tcut the build time\n"))


class SourcesCase(ClaimsCase):
    """ClaimsCase with L2's sources written under the working folder."""

    def setUp(self):
        super().setUp()
        self.put("evidence/offer.txt", OFFER)
        self.put("evidence/review.txt", REVIEW)
        self.put("evidence/bad.txt", b"Dana Example \xff\xfe will lead a group of six engineers\n")
        self.put("evidence/offer.pdf", b"%PDF-1.4 invented\n")
        os.symlink("gone.txt", os.path.join(self.dir, "evidence", "link.txt"))

    def put(self, name, data):
        path = os.path.join(self.dir, name)
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        mode = "wb" if isinstance(data, bytes) else "w"
        kwargs = {} if mode == "wb" else {"encoding": "utf-8", "newline": ""}
        with open(path, mode, **kwargs) as handle:
            handle.write(data)

    def sources(self, list_text, text=SIX, control="example", extra=(), flag=True,
                list_name=L2_NAME, path=SYSTEM_PATH):
        """Write the list and f.txt, run the gate; (code, out, err)."""
        self.put(list_name, list_text)
        self.put("f.txt", text)
        args = (["--list", list_name, "--control", control] + list(extra)
                + (["--check-sources"] if flag else []) + ["f.txt"])
        return self.claims(args, path=path)

    def known(self, key):
        list_text, text, control, extra, out, code = KNOWN[key]
        return self.sources(list_text, text, control, extra), (code, out, "")

    def variant(self, key):
        list_text, body, alone, out, code = VARIANTS[key]
        old = os.path.join(self.bin, "pdftotext")
        if os.path.lexists(old):
            os.remove(old)
        if body is not None:
            stand_in(self.bin, body)
        path = self.bin if alone else SYSTEM_PATH
        return self.sources(list_text, path=path), (code, out, "")

    def nested(self, list_text=L2, decoy=True):
        """Spec 9.25: the list at lists/, its sources at lists/evidence/, decoys at evidence/."""
        self.put("lists/" + L2_NAME, list_text)
        self.put("lists/evidence/offer.txt", OFFER)
        self.put("lists/evidence/review.txt", REVIEW)
        if decoy:
            self.put("evidence/offer.txt", "Dana Example led nobody. %s.\n" % MARK)
            self.put("evidence/review.txt", "Dana Example will cut the build time in half.\n")
        self.put("f.txt", SIX)
        return self.claims(["--list", "lists/" + L2_NAME, "--control", "example",
                            "--check-sources", "f.txt"])


# ---------------------------------------------------------------- the known answers

class KnownAnswers(SourcesCase):
    def test_9_20_found_approved_proposed_not_found_refused_and_unquoted_untouched(self):
        got, expected = self.known(20)
        self.assertEqual(got, expected)

    def test_9_21_an_approved_quote_not_found_exits_1_with_an_ok_file(self):
        got, expected = self.known(21)
        self.assertEqual(got, expected)

    def test_9_22_an_approved_source_unreadable_exits_2(self):
        got, expected = self.known(22)
        self.assertEqual(got, expected)

    def test_9_23_an_approved_quote_unverified_does_not_change_the_exit(self):
        got, expected = self.known(23)
        self.assertEqual(got, expected)

    def test_9_24_proposed_results_never_change_the_exit(self):
        got, expected = self.known(24)
        self.assertEqual(got, expected)

    def test_9_25_the_source_is_relative_to_the_list_file(self):
        self.assertEqual(self.nested(), (0, KNOWN[20][4], ""))

    def test_9_25_an_absolute_source(self):
        absolute = os.path.join(self.dir, "lists", "evidence", "offer.txt")
        got = self.nested(first_source(absolute))
        self.assertEqual(got, (0, KNOWN[20][4], ""))

    def test_9_26_exit_precedence(self):
        for key in ("26a", "26b", "26c"):
            with self.subTest(case=key):
                got, expected = self.known(key)
                self.assertEqual(got, expected)

    def test_9_27_order_file_lines_stale_lines_source_lines_counts(self):
        for key in ("27a", "27b"):
            with self.subTest(case=key):
                got, expected = self.known(key)
                self.assertEqual(got, expected)

    def test_9_28_list_errors_with_and_without_the_flag(self):
        for list_text, err in LIST_ERRORS:
            for flag in (True, False):
                with self.subTest(err=err, flag=flag, list_text=list_text[-40:]):
                    self.assertEqual(self.sources(list_text, flag=flag), (2, "", err))

    def test_9_29_a_quote_line_takes_no_entry_number(self):
        got, expected = self.known(29)
        self.assertEqual(got, expected)
        without = fail("f.txt", 1, 2) + finding("f.txt", 1, "proposed, entry #3",
                                                "Cut build times by forty percent.")
        self.assertEqual(self.sources(L2, KNOWN[29][1], flag=False), (1, without, ""))

    def test_9_30_quote_in_capitals_and_a_note_after_the_quote(self):
        got, expected = self.known(30)
        self.assertEqual(got, expected)

    def test_9_31_no_quotes_prints_two_zero_count_lines(self):
        got, expected = self.known(31)
        self.assertEqual(got, expected)

    def test_9_32_flag_parsing(self):
        once = self.sources(L2)
        self.assertEqual(self.sources(L2, extra=["--check-sources"]), once)
        self.assertEqual(self.sources(L2, extra=["--check-sources", "--check-sources"]), once)
        self.put("f.txt", SIX)
        self.assertEqual(
            self.claims(["--list", L2_NAME, "--control", "example", "--check-sources=1",
                         "f.txt"]),
            (2, "", "cannot run: unknown option --check-sources=1\n"))
        self.assertEqual(
            self.claims(["--list", L2_NAME, "--control", "--check-sources", "f.txt"]),
            (2, "", "cannot run: --control needs a value\n"))
        for args in (["--help", "--check-sources"], ["--check-sources", "-h"],
                     ["--list", L2_NAME, "--check-sources", "--help", "f.txt"]):
            with self.subTest(args=args):
                self.assertEqual(self.claims(args), (0, HELP, ""))

    def test_9_33_no_quote_source_source_text_note_or_list_path_reaches_any_output(self):
        outputs = []
        for key in KNOWN:
            got, _expected = self.known(key)
            outputs.append(got)
        for key in VARIANTS:
            got, _expected = self.variant(key)
            outputs.append(got)
        outputs.append(self.nested())
        outputs.append(self.nested(first_source(
            os.path.join(self.dir, "lists", "evidence", "offer.txt"))))
        secrets = SECRETS + (self.dir, os.path.realpath(self.dir), self._tmp.name)
        self.assertGreater(len(outputs), 25)
        for code, out, err in outputs:
            for secret in secrets:
                self.assertNotIn(secret, out)
                self.assertNotIn(secret, err)

    def test_9_34_without_the_flag_quote_lines_change_nothing(self):
        self.put("l1q.tsv", L1_QUOTED)
        for number in range(1, 14):
            text, control, extra, _out, _code = CASES[number]
            with self.subTest(case=number):
                plain = self.gate(text, control=control, extra=extra)
                quoted = self.gate(text, control=control, extra=extra, list_name="l1q.tsv")
                self.assertEqual(quoted, plain)


# ---------------------------------------------------------------- other runs

class Variations(SourcesCase):
    def check_variant(self, key):
        got, expected = self.variant(key)
        self.assertEqual(got, expected)

    def test_a_source_that_is_not_utf8_is_unreadable(self):
        self.check_variant("not UTF-8")

    def test_a_directory_source_is_unreadable(self):
        self.check_variant("directory")

    def test_a_dangling_symbolic_link_is_unreadable_not_unverified(self):
        self.check_variant("dangling link")

    def test_a_pdf_source_with_no_pdftotext_is_unreadable(self):
        self.check_variant("pdftotext missing")

    def test_a_pdf_source_whose_pdftotext_fails_is_unreadable(self):
        self.check_variant("pdftotext fails")

    def test_a_pdf_source_read_through_a_stand_in(self):
        self.check_variant("pdf found")
        self.check_variant("pdf not found")

    def test_a_url_a_record_id_and_a_missing_path_are_unverified(self):
        for key in ("url", "record id", "missing path"):
            with self.subTest(case=key):
                self.check_variant(key)

    def test_a_proposed_quote_not_found_alone_exits_0(self):
        self.check_variant("proposed not found only")

    def test_a_refused_quote_is_never_checked_or_counted(self):
        self.check_variant("refused unreadable only")

    def test_an_entry_with_a_source_and_no_quote_is_not_counted(self):
        self.check_variant("source and no quote")

    def test_blank_and_comment_lines_between_entry_and_quote_are_skipped(self):
        self.check_variant("blank and comment lines before the quote")

    def test_the_decoy_alone_is_not_read(self):
        """Without lists/evidence/offer.txt the source is unverified, though evidence/ holds one."""
        self.put("lists/" + L2_NAME, L2)
        self.put("f.txt", SIX)
        got = self.claims(["--list", "lists/" + L2_NAME, "--control", "example",
                           "--check-sources", "f.txt"])
        self.assertEqual(got, (0, ok("f.txt", 1) + line("approved", 1, "source unverified")
                               + line("proposed", 3, "source unverified")
                               + counts((0, 0, 0, 1), (0, 0, 0, 1)), ""))

    def test_the_source_check_runs_beside_a_dead_input(self):
        self.put(L2_NAME, L2)
        got = self.claims(["--list", L2_NAME, "--control", "example", "--check-sources",
                           "no-such-file.txt"])
        self.assertEqual(got, (2, "DEAD  no-such-file.txt: cannot read\n" + ENTRY_3
                               + counts((1, 0, 0, 0), (0, 1, 0, 0)), ""))

    def test_the_existing_cannot_run_errors_are_unchanged_by_quote_lines(self):
        listed = L2 + "maybe\tExample.\n"
        self.assertEqual(self.sources(listed), (2, "", "cannot run: unknown status in entry #5\n"))
        listed = L2 + "approved\tled a team of six engineers at example corp\n"
        self.assertEqual(self.sources(listed),
                         (2, "", "cannot run: entries #1 and #5 are the same sentence\n"))
        listed = L2 + "approved\n"
        self.assertEqual(self.sources(listed), (2, "", "cannot run: entry #5 has no sentence\n"))


if __name__ == "__main__":
    unittest.main()
