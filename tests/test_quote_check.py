"""Tests for ``career_track_record.quote_check``. All data here is invented.

Every source and quote below is made up (Example Corp., the Example importer). Files are written
into a temporary folder at run time; no fixture file is used. PDF cases put a small stand-in
``pdftotext`` alone on PATH. Invisible characters, hyphens and curly quotes are written as
escapes, never raw. The timing pins each run in a fresh interpreter with a ten second limit.
"""

import contextlib
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import quote_check  # noqa: E402
from career_track_record.quote_check import DEAD, FOUND, NOT_FOUND, check_quote  # noqa: E402

FOUND_T = (FOUND, "")
NOT_FOUND_T = (NOT_FOUND, "")


def stand_in(directory, body):
    path = os.path.join(directory, "pdftotext")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IRUSR)


class QuoteCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = os.path.join(self._tmp.name, "work")
        self.bin = os.path.join(self._tmp.name, "bin")
        os.mkdir(self.dir)
        os.mkdir(self.bin)

    def write(self, name, data):
        mode = "wb" if isinstance(data, bytes) else "w"
        kwargs = {} if mode == "wb" else {"encoding": "utf-8", "newline": ""}
        path = os.path.join(self.dir, name)
        with open(path, mode, **kwargs) as handle:
            handle.write(data)
        return path

    def check(self, quote, data, name="source.txt"):
        return check_quote(quote, self.write(name, data))

    def pdf(self, quote, body, name="source.pdf"):
        """Run a PDF check with a stand-in pdftotext alone on PATH."""
        path = self.write(name, b"%PDF-1.4 invented\n")
        stand_in(self.bin, body)
        with mock.patch.dict(os.environ, {"PATH": self.bin}):
            return check_quote(quote, path)

    # ------------------------------------------------------------ A. found

    def test_found_plain(self):
        self.assertEqual(self.check("led a team", "She led a team of six.\n"), FOUND_T)

    def test_found_different_case(self):
        self.assertEqual(self.check("LED A TEAM", "She led a team of six.\n"), FOUND_T)

    def test_found_across_a_line_break(self):
        self.assertEqual(self.check("led a team", "She led\na team of six.\n"), FOUND_T)

    def test_found_curly_quotes_against_straight(self):
        source = "He said \u201cthe importer\u2019s speed\u201d was fine.\n"
        self.assertEqual(self.check("\"the importer's speed\"", source), FOUND_T)

    def test_found_special_hyphen_against_plain(self):
        self.assertEqual(self.check("end-to-end", "An end\u2011to\u2011end run.\n"), FOUND_T)

    def test_found_ligature(self):
        self.assertEqual(self.check("final", "The \ufb01nal report.\n"), FOUND_T)

    def test_found_zero_width_space_inside_a_word(self):
        self.assertEqual(self.check("importer", "The impor\u200bter ran.\n"), FOUND_T)

    def test_found_line_end_wrap_joined(self):
        self.assertEqual(
            self.check("cross-functional", "A cross-\nfunctional team.\n"), FOUND_T)

    def test_found_quote_with_final_stop_where_source_continues(self):
        self.assertEqual(
            self.check("Shipped the Example importer.", "Shipped the Example importer, then left.\n"),
            FOUND_T)

    def test_found_at_the_very_start_and_end(self):
        self.assertEqual(self.check("Example Corp", "Example Corp is here"), FOUND_T)
        self.assertEqual(self.check("is here", "Example Corp is here"), FOUND_T)

    def test_found_dot_net_inside_asp_net(self):
        self.assertEqual(self.check(".NET", "We used ASP.NET daily.\n"), FOUND_T)

    def test_found_c_plus_plus_inside_c_plus_plus_11(self):
        self.assertEqual(self.check("C++", "We used C++11.\n"), FOUND_T)

    def test_found_crlf_source(self):
        self.assertEqual(self.check("led a team", b"She led\r\na team.\r\n"), FOUND_T)

    def test_found_source_with_byte_order_mark(self):
        self.assertEqual(self.check("led a team", b"\xef\xbb\xbfled a team of six.\n"), FOUND_T)

    # ------------------------------------------------------- B. not found

    def test_not_found_one_word_changed(self):
        self.assertEqual(self.check("led a crew", "She led a team of six.\n"), NOT_FOUND_T)

    def test_not_found_start_boundary(self):
        self.assertEqual(self.check("led a team", "She misled a team of six.\n"), NOT_FOUND_T)

    def test_not_found_end_boundary(self):
        self.assertEqual(self.check("led a team", "She led a teammate.\n"), NOT_FOUND_T)

    def test_not_found_both_boundaries(self):
        self.assertEqual(self.check("led a team", "She misled a teammate.\n"), NOT_FOUND_T)

    def test_not_found_quote_longer_than_source(self):
        self.assertEqual(
            self.check("led a team of six engineers at Example Corp", "led a team"), NOT_FOUND_T)

    def test_not_found_empty_source(self):
        self.assertEqual(self.check("led a team", ""), NOT_FOUND_T)

    # ------------------------------------------------------------ C. dead

    def test_dead_empty_quote(self):
        self.assertEqual(self.check("", "led a team"), (DEAD, "no quote"))

    def test_dead_blank_quote(self):
        self.assertEqual(self.check("   \n\t", "led a team"), (DEAD, "no quote"))

    def test_dead_punctuation_only_quote(self):
        self.assertEqual(self.check("...", "led a team..."), (DEAD, "no quote"))

    def test_dead_zero_width_only_quote(self):
        self.assertEqual(self.check("\u200b\u200d", "led a team"), (DEAD, "no quote"))

    def test_dead_none_quote(self):
        self.assertEqual(self.check(None, "led a team"), (DEAD, "no quote"))

    def test_dead_missing_file_and_directory(self):
        missing = os.path.join(self.dir, "nope.txt")
        self.assertEqual(check_quote("led a team", missing), (DEAD, "cannot read"))
        self.assertEqual(check_quote("led a team", self.dir), (DEAD, "cannot read"))

    def test_dead_none_path(self):
        self.assertEqual(check_quote("led a team", None), (DEAD, "cannot read"))

    def test_dead_not_utf_8(self):
        self.assertEqual(self.check("led a team", b"led a team \xff\xfe\n"), (DEAD, "not UTF-8"))

    def test_dead_pdf_without_pdftotext(self):
        path = self.write("source.pdf", b"%PDF-1.4 invented\n")
        with mock.patch.dict(os.environ, {"PATH": self.bin}):
            self.assertEqual(check_quote("led a team", path), (DEAD, "pdftotext not found"))

    def test_dead_pdf_stand_in_exits_one(self):
        self.assertEqual(self.pdf("led a team", "exit 1\n"), (DEAD, "pdftotext failed"))

    def test_pdf_stand_in_text_found_and_not_found(self):
        body = "printf 'She led a team of six.\\n'\n"
        self.assertEqual(self.pdf("led a team", body), FOUND_T)
        self.assertEqual(self.pdf("led a crew", body), NOT_FOUND_T)
        self.assertEqual(self.pdf("misled a team", body), NOT_FOUND_T)

    def test_upper_case_pdf_name_goes_through_pdftotext(self):
        body = "printf 'She led a team of six.\\n'\n"
        self.assertEqual(self.pdf("led a team", body, name="SOURCE.PDF"), FOUND_T)

    def test_pdf_path_starting_with_a_dash(self):
        self.write("-dash.pdf", b"%PDF-1.4 invented\n")
        stand_in(self.bin, "printf 'She led a team of six.\\n'\n")
        before = os.getcwd()
        os.chdir(self.dir)
        try:
            with mock.patch.dict(os.environ, {"PATH": self.bin}):
                self.assertEqual(check_quote("led a team", "-dash.pdf"), FOUND_T)
        finally:
            os.chdir(before)

    # ---------------------------------------------------- D. timing pins

    def run_pin(self, setup, expected):
        code = (
            "from career_track_record.quote_check import check_quote\n"
            "import os, sys, tempfile\n"
            + setup +
            "d = tempfile.mkdtemp()\n"
            "p = os.path.join(d, 's.txt')\n"
            "open(p, 'w', encoding='utf-8').write(s)\n"
            "r = check_quote(q, p)\n"
            "os.remove(p)\n"
            "os.rmdir(d)\n"
            "print(r[0])\n"
        )
        try:
            done = subprocess.run(
                [sys.executable, "-c", code], timeout=10,
                env=dict(os.environ, PYTHONPATH=SRC), capture_output=True)
        except subprocess.TimeoutExpired:
            self.fail("the search did not finish within 10 seconds")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.decode().strip(), expected)

    def test_timing_one_long_word_run(self):
        self.run_pin("s = 'a' * 2_000_000\nq = 'a' * 10_000\n", NOT_FOUND)

    def test_timing_many_short_words(self):
        self.run_pin("s = 'a ' * 1_000_000\nq = 'a ' * 2_000 + 'b'\n", NOT_FOUND)

    def test_timing_many_medium_runs(self):
        self.run_pin("s = ('ab' * 500 + ' ') * 2_000\nq = 'ab' * 400\n", NOT_FOUND)

    def test_timing_late_match_in_long_source(self):
        self.run_pin(
            "s = 'word ' * 400_000 + 'Example importer'\nq = 'Example importer'\n", FOUND)

    # ----------------------------------------------------------- E. quiet

    def test_nothing_is_printed(self):
        out = io.StringIO()
        err = io.StringIO()
        path = self.write("source.txt", "She led a team of six.\n")
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(check_quote("led a team", path), FOUND_T)
            self.assertEqual(check_quote("led a crew", path), NOT_FOUND_T)
            self.assertEqual(check_quote("", path), (DEAD, "no quote"))
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))

    # ------------------------------------------------------ F. known limits

    # Known limit: pdftotext removes the hyphen of a wrap inside a page, so the quote is not found.
    def test_limit_pdf_wrap_inside_a_page(self):
        self.assertEqual(self.pdf("zebra-word", "printf 'zebraword\\n'\n"), NOT_FOUND_T)

    # Known limit: a word hyphenated by layout keeps its hyphen after the join, so it is not found.
    def test_limit_word_hyphenated_by_layout(self):
        self.assertEqual(self.check("experience", "Her experi-\nence grew.\n"), NOT_FOUND_T)

    # Known limit: Office files are not read; a .docx is bytes that are not UTF-8 text.
    def test_limit_docx_is_not_read(self):
        self.assertEqual(
            self.check("led a team", b"PK\x03\x04\x14\x00\x06\x00\x80\x81", name="source.docx"),
            (DEAD, "not UTF-8"))


if __name__ == "__main__":
    unittest.main()
