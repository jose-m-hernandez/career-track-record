"""Tests for ``track-record record``: bad input, DEAD checks, the self-test, the sentinel and
the read-only rule. Every table, declaration and value here is invented. The sentinel and
traceback checks of ``RecordCase.tearDown`` apply to every run these tests make.
"""

import csv
import hashlib
import io
import os
import shutil
import sys
import unittest
import unittest.mock

from tests import test_record_check as base
from tests.test_record_check import SENTINEL, k, section, tsv

ROOT = base.ROOT
KNOWN = base.KNOWN
SENTINEL_DIR = os.path.join(ROOT, "tests", "fixtures", "record", "sentinel")

from career_track_record import record_check  # noqa: E402

TABLES = "tables:\n  a | a.tsv | tsv | k\n"
KNOWN_DECLARATION = os.path.join(KNOWN, "record.txt")


def readable_despite_mode_zero(path):
    return os.access(path, os.R_OK)


class DeclarationProblemTest(base.RecordCase):
    CASES = [
        ("a table with three fields", "tables:\n  a | a.tsv | tsv\n",
         ["declaration line 2: a table is written: name | file | format | key column"]),
        ("a table with five fields", "tables:\n  a | a.tsv | tsv | k | x\n",
         ["declaration line 2: a table is written: name | file | format | key column"]),
        ("a table name outside the set", "tables:\n  a_b | a.tsv | tsv | k\n",
         ["declaration line 2: a table name holds letters, digits and - only: a_b"]),
        ("a table name with an accent", "tables:\n  caf" + chr(0xE9) + " | a.tsv | tsv | k\n",
         ["declaration line 2: a table name holds letters, digits and - only: caf" + chr(0xE9)]),
        ("a table named twice", TABLES + "  a | b.tsv | tsv | k\n",
         ["declaration line 3: the table a is named twice"]),
        ("a table item repeated", TABLES + "  a | a.tsv | tsv | k\n",
         ["declaration line 3: the same item as line 2"]),
        ("a reference item repeated",
         TABLES + "references:\n  a | c | a | k | single\n  a | c | a | k | single\n",
         ["declaration line 5: the same item as line 4"]),
        ("an item repeated after trimming its fields",
         TABLES + "required:\n  a | c\n  a   |   c  \n",
         ["declaration line 5: the same item as line 4"]),
        ("an item repeated a third time names the first",
         TABLES + "dates:\n  a | c\n  a | d\n  a | c\n  a | c\n",
         ["declaration line 6: the same item as line 4",
          "declaration line 7: the same item as line 4"]),
        ("a format that is neither", "tables:\n  a | a.tsv | json | k\n",
         ["declaration line 2: a format is tsv or csv: json"]),
        ("a format in capitals", "tables:\n  a | a.tsv | TSV | k\n",
         ["declaration line 2: a format is tsv or csv: TSV"]),
        ("a reference with four fields", TABLES + "references:\n  a | c | a | k\n",
         ["declaration line 4: a reference is written: table | column | table | column | rule"]),
        ("a reference with six fields", TABLES + "references:\n  a | c | a | k | single | x\n",
         ["declaration line 4: a reference is written: table | column | table | column | rule"]),
        ("a reference from an unknown table", TABLES + "references:\n  yy | c | a | k | single\n",
         ["declaration line 4: no table named yy"]),
        ("a reference to an unknown table", TABLES + "references:\n  a | c | zz | k | single\n",
         ["declaration line 4: no table named zz"]),
        ("a reference with two unknown tables", TABLES + "references:\n  yy | c | zz | k | single\n",
         ["declaration line 4: no table named yy"]),
        ("an unknown rule", TABLES + "references:\n  a | c | a | k | many\n",
         ["declaration line 4: a rule is single, list CHARACTERS or pattern REGEX: many"]),
        ("a list with no characters", TABLES + "references:\n  a | c | a | k | list\n",
         ["declaration line 4: a rule is single, list CHARACTERS or pattern REGEX: list"]),
        ("a pattern with no regex", TABLES + "references:\n  a | c | a | k | pattern\n",
         ["declaration line 4: a rule is single, list CHARACTERS or pattern REGEX: pattern"]),
        ("single with an argument", TABLES + "references:\n  a | c | a | k | single x\n",
         ["declaration line 4: a rule is single, list CHARACTERS or pattern REGEX: single x"]),
        ("a rule in capitals", TABLES + "references:\n  a | c | a | k | List ,\n",
         ["declaration line 4: a rule is single, list CHARACTERS or pattern REGEX: List ,"]),
        ("a space as a separator", TABLES + "references:\n  a | c | a | k | list , ;\n",
         ["declaration line 4: a space cannot be a list separator"]),
        ("a pattern that does not compile", TABLES + "references:\n  a | c | a | k | pattern (\n",
         ["declaration line 4: not a valid pattern: ("]),
        ("a pattern with a huge repeat", TABLES + "references:\n  a | c | a | k | pattern a{99999999999}\n",
         ["declaration line 4: not a valid pattern: a{99999999999}"]),
        ("a long pattern that does not compile",
         TABLES + "references:\n  a | c | a | k | pattern " + "(" * 50 + "\n",
         ["declaration line 4: not a valid pattern: " + "(" * 50]),
        ("required with one field", TABLES + "required:\n  a\n",
         ["declaration line 4: required is written: table | column"]),
        ("required with three fields", TABLES + "required:\n  a | c | d\n",
         ["declaration line 4: required is written: table | column"]),
        ("required of an unknown table", TABLES + "required:\n  zz | c\n",
         ["declaration line 4: no table named zz"]),
        ("values with two fields", TABLES + "values:\n  a | g\n",
         ["declaration line 4: values is written: table | column | value | ..."]),
        ("values of an unknown table", TABLES + "values:\n  zz | g | A\n",
         ["declaration line 4: no table named zz"]),
        ("dates with three fields", TABLES + "dates:\n  a | c | d\n",
         ["declaration line 4: dates is written: table | column"]),
        ("dates of an unknown table", TABLES + "dates:\n  zz | c\n",
         ["declaration line 4: no table named zz"]),
        ("corrections with two fields", TABLES + "corrections:\n  a | c\n",
         ["declaration line 4: corrections is written: table | column | date column"]),
        ("corrections of an unknown table", TABLES + "corrections:\n  zz | c | d\n",
         ["declaration line 4: no table named zz"]),
        ("earlier with one field", TABLES + "earlier:\n  a\n",
         ["declaration line 4: earlier is written: table | file"]),
        ("earlier of an unknown table", TABLES + "earlier:\n  zz | f\n",
         ["declaration line 4: no table named zz"]),
        ("an empty declaration", "", ["cannot run: the declaration names no table"]),
        ("only comments and blank lines", "# nothing\n\n   \n# more\n",
         ["cannot run: the declaration names no table"]),
        ("tables with no item", "tables:\n", ["cannot run: the declaration names no table"]),
        ("no tables key at all", "required:\n  a | c\n",
         ["cannot run: declaration line 2: no table named a",
          "cannot run: the declaration names no table"]),
        ("an unknown key", TABLES + "bogus:\n",
         ["declaration line 3: unknown key bogus"]),
        ("a repeated key", TABLES + "tables:\n",
         ["declaration line 3: the key tables is given twice"]),
        ("an empty field", "tables:\n  a |  | tsv | k\n",
         ["declaration line 2: an empty field"]),
        ("a line that is not key and value", "tables\n",
         ["declaration line 1: not a key: value line",
          "cannot run: the declaration names no table"]),
        ("a value on the key line", "tables: a | a.tsv | tsv | k\n",
         ["declaration line 1: tables is a list: write its items on indented lines",
          "cannot run: the declaration names no table"]),
        ("an indented line under no key", "  a | a.tsv | tsv | k\n" + TABLES,
         ["declaration line 1: an indented line that belongs to no key"]),
        ("a control character in a name", "tables:\n  a" + chr(7) + "b | a.tsv | tsv | k\n",
         ["declaration line 2: a table name holds letters, digits and - only: a\\x07b"]),
        ("a long name is cut at 40", "tables:\n  " + "x" * 45 + "_ | a.tsv | tsv | k\n",
         ["declaration line 2: a table name holds letters, digits and - only: "
          + "x" * 40 + "..."]),
        ("problems come in line order, one line each",
         "tables:\n  a | a.tsv | tsv\nbogus:\nrequired:\n  zz | c\n  a | c | d\n",
         ["declaration line 2: a table is written: name | file | format | key column",
          "declaration line 3: unknown key bogus", "declaration line 5: no table named zz",
          "declaration line 6: required is written: table | column"]),
    ]

    def test_each_problem_has_its_line_and_exits_2_with_nothing_on_stdout(self):
        for label, text, want in self.CASES:
            with self.subTest(label):
                for extra in ([], ["--report-only"]):
                    folder = self.folder()
                    folder.put("record.txt", text)
                    code, out, err = self.cli(["record"] + extra + [folder.path("record.txt")])
                    lines = [line if line.startswith("cannot run: ") else "cannot run: " + line
                             for line in want]
                    self.assertEqual((code, out, err), (2, "", "".join(l + "\n" for l in lines)))

    def test_the_same_item_under_two_keys_is_not_a_repeat(self):
        files = {"a.tsv": tsv([["k", "c"], [k(1), "2026-01-05"]])}
        code, lines = self.lines(TABLES + "required:\n  a | c\ndates:\n  a | c\n", files)
        self.assertEqual((code, lines[-1]), (0, "checks: OK 3, FAIL 0, DEAD 0"))

    def test_a_deeply_nested_pattern_never_shows_a_traceback(self):
        text = TABLES + "references:\n  a | c | a | k | pattern " + "(" * 3000 + ")" * 3000 + "\n"
        folder = self.folder()
        folder.put("record.txt", text)
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("cannot run: "))
        self.assertEqual(err.count("\n"), 1)


class CommandLineTest(base.RecordCase):
    def test_a_command_line_that_cannot_run_names_one_reason(self):
        folder = self.folder()
        folder.put("record.txt", TABLES)
        path = folder.path("record.txt")
        newline_option = "--bo" + chr(10) + "gus"
        cases = [
            ([], "cannot run: record needs a DECLARATION file\n"),
            (["--report-only"], "cannot run: record needs a DECLARATION file\n"),
            (["--"], "cannot run: record needs a DECLARATION file\n"),
            ([path, path], "cannot run: record takes one DECLARATION file, not several\n"),
            ([path, "--", path], "cannot run: record takes one DECLARATION file, not several\n"),
            (["--bogus"], "cannot run: unknown option --bogus\n"),
            (["--bogus", path], "cannot run: unknown option --bogus\n"),
            ([path, "-x"], "cannot run: unknown option -x\n"),
            (["--bogus=" + SENTINEL], "cannot run: unknown option --bogus\n"),
            (["--report-only=x", path], "cannot run: --report-only takes no value\n"),
            (["--report-only=", path], "cannot run: --report-only takes no value\n"),
            ([newline_option], "cannot run: unknown option --bo\\ngus\n"),
            (["--bogus", "--report-only=x"], "cannot run: unknown option --bogus\n"),
            (["--report", path], "cannot run: unknown option --report\n"),
            (["--report-o", path], "cannot run: unknown option --report-o\n"),
            (["--report=x", path], "cannot run: unknown option --report\n"),
        ]
        for args, want in cases:
            with self.subTest(args):
                self.assertEqual(self.cli(["record"] + args), (2, "", want))

    def test_an_unknown_subcommand_like_word_is_a_file_name_to_record(self):
        code, out, err = self.cli(["record", "freeze"])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "cannot run: cannot read the declaration: freeze\n")

    def test_a_declaration_path_with_a_nul_character(self):
        code, out, err = self.cli(["record", "x" + chr(0) + "y"])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "cannot run: cannot read the declaration: x\\x00y\n")

    def test_a_missing_declaration(self):
        folder = self.folder()
        code, out, err = self.cli(["record", folder.path("nothing.txt")])
        self.assertEqual((code, out, err),
                         (2, "", "cannot run: cannot read the declaration: nothing.txt\n"))

    def test_a_folder_as_the_declaration(self):
        folder = self.folder()
        os.mkdir(folder.path("sub"))
        for name in ("sub", "sub" + os.sep):
            with self.subTest(name):
                code, out, err = self.cli(["record", folder.path(name)])
                self.assertEqual((code, out, err),
                                 (2, "", "cannot run: cannot read the declaration: sub\n"))

    def test_an_unreadable_declaration(self):
        folder = self.folder()
        folder.put("record.txt", TABLES)
        os.chmod(folder.path("record.txt"), 0)
        self.addCleanup(os.chmod, folder.path("record.txt"), 0o600)
        if readable_despite_mode_zero(folder.path("record.txt")):
            self.skipTest("this account reads a file with mode 0")
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual((code, out, err),
                         (2, "", "cannot run: cannot read the declaration: record.txt\n"))

    def test_a_declaration_that_is_not_utf_8(self):
        folder = self.folder()
        folder.put("record.txt", b"tables:\n  a | a" + b"\xff" + b".tsv | tsv | k\n")
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual((code, out, err),
                         (2, "", "cannot run: the declaration is not valid UTF-8: record.txt\n"))

    def test_a_byte_order_mark_on_the_declaration_is_dropped(self):
        folder = self.folder()
        folder.put("a.tsv", tsv([["k"], [k(1)]]))
        folder.put("record.txt", b"\xef\xbb\xbf" + TABLES.encode("utf-8"))
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("OK    table a: "))

    def test_a_declaration_with_crlf_and_lone_cr_line_ends(self):
        for eol in ("\r\n", "\r"):
            with self.subTest(repr(eol)):
                folder = self.folder()
                folder.put("a.tsv", tsv([["k"], [k(1)]]))
                folder.put("record.txt", TABLES.replace("\n", eol))
                code, out, err = self.cli(["record", folder.path("record.txt")])
                self.assertEqual((code, err), (0, ""))

    def test_a_name_with_a_line_break_or_a_control_character_is_escaped(self):
        folder = self.folder()
        for name, shown in (("x" + chr(10) + "y.txt", "x\\ny.txt"),
                            ("x" + chr(7) + "y.txt", "x\\x07y.txt"),
                            ("x" + chr(13) + "y.txt", "x\\ry.txt"),
                            ("x" + chr(0x200B) + "y.txt", "x\\" + "u200by.txt")):
            with self.subTest(shown):
                code, out, err = self.cli(["record", folder.path(name)])
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(err, "cannot run: cannot read the declaration: %s\n" % shown)

    def test_a_name_with_a_line_break_is_escaped_when_the_file_exists_and_is_not_utf_8(self):
        folder = self.folder()
        name = "x" + chr(10) + "y.txt"
        folder.put(name, b"\xff")
        code, out, err = self.cli(["record", folder.path(name)])
        self.assertEqual(err, "cannot run: the declaration is not valid UTF-8: x\\ny.txt\n")

    def test_a_fifo_as_the_declaration_is_never_opened(self):
        folder = self.folder()
        os.mkfifo(folder.path("record.txt"))
        code, out, err = self.sub(["record", folder.path("record.txt")], timeout=20)
        self.assertEqual((code, out, err),
                         (2, "", "cannot run: cannot read the declaration: record.txt\n"))

    def test_a_fifo_as_a_table_and_as_an_earlier_copy_is_never_opened(self):
        folder = self.folder()
        os.mkfifo(folder.path("a.tsv"))
        os.mkfifo(folder.path("old.tsv"))
        folder.put("record.txt", TABLES + "earlier:\n  a | old.tsv\n")
        code, out, err = self.sub(["record", folder.path("record.txt")], timeout=20)
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out, "DEAD  table a: not a regular file\n"
                              "DEAD  earlier a: not a regular file\n"
                              "checks: OK 0, FAIL 0, DEAD 2\n")
        folder.put("b.tsv", tsv([["k"], [k(1)]]))
        folder.put("record.txt", "tables:\n  a | b.tsv | tsv | k\nearlier:\n  a | old.tsv\n")
        code, out, err = self.sub(["record", folder.path("record.txt")], timeout=20)
        self.assertIn("DEAD  earlier a: earlier copy not a regular file\n", out)

    def test_closed_standard_output_is_one_line_on_standard_error(self):
        for args in (["record", KNOWN_DECLARATION], ["record", "--report-only", KNOWN_DECLARATION],
                     ["record", "--help"]):
            with self.subTest(args):
                code, out, err = self.sub(args, shell_tail=">&-")
                self.assertEqual((code, out, err), (2, "", base.NO_OUTPUT))

    def test_a_pipe_whose_reader_is_gone_is_the_same_failure(self):
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            p = base.subprocess.run(base.CMD + ["record", KNOWN_DECLARATION], env=base.env(),
                                    stdin=base.subprocess.DEVNULL, stdout=write_end,
                                    stderr=base.subprocess.PIPE, timeout=30)
        finally:
            os.close(write_end)
        self.assertEqual((p.returncode, p.stderr.decode("utf-8")), (2, base.NO_OUTPUT))


class DeadTest(base.RecordCase):
    def dead(self, declaration, files, line, label=None):
        """The declaration's one DEAD check has ``line``; exit 2 with and without the option."""
        for extra in (False, True):
            code, lines = self.lines(declaration, files, report_only=extra)
            self.assertEqual(code, 2)
            found = [l for l in lines if l.startswith("DEAD")]
            self.assertIn(line, found)

    def table_reason(self, files, line, fmt="tsv", name="a.tsv"):
        declaration = "tables:\n  a | %s | %s | k\n" % (name, fmt)
        for extra in (False, True):
            code, lines = self.lines(declaration, files, report_only=extra)
            self.assertEqual((code, lines), (2, [line, "checks: OK 0, FAIL 0, DEAD 1"]))

    def test_a_missing_file(self):
        self.table_reason({}, "DEAD  table a: file missing")

    def test_a_folder_is_not_a_regular_file(self):
        folder = self.folder()
        os.mkdir(folder.path("a.tsv"))
        folder.put("record.txt", TABLES)
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual((code, out.split("\n")[0]), (2, "DEAD  table a: not a regular file"))

    def test_a_file_that_cannot_be_read(self):
        folder = self.folder()
        folder.put("a.tsv", tsv([["k"], [k(1)]]))
        folder.put("record.txt", TABLES)
        os.chmod(folder.path("a.tsv"), 0)
        self.addCleanup(os.chmod, folder.path("a.tsv"), 0o600)
        if readable_despite_mode_zero(folder.path("a.tsv")):
            self.skipTest("this account reads a file with mode 0")
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual((code, out.split("\n")[0]), (2, "DEAD  table a: cannot be read"))

    def test_a_link_to_a_file_is_followed_and_a_dangling_link_is_missing(self):
        folder = self.folder()
        folder.put("real.tsv", tsv([["k"], [k(1)]]))
        os.symlink("real.tsv", folder.path("a.tsv"))
        folder.put("record.txt", TABLES + "  b | gone.tsv | tsv | k\n")
        os.symlink("nowhere.tsv", folder.path("gone.tsv"))
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual(out.split("\n")[:2], [
            "OK    table a: " + base.table_counts(1, 0, 0, 0, 0), "DEAD  table b: file missing"])

    def test_a_path_under_a_file_is_missing_and_a_path_with_a_nul_cannot_be_read(self):
        folder = self.folder()
        folder.put("plain.txt", b"x")
        folder.put("record.txt", "tables:\n  a | plain.txt/a.tsv | tsv | k\n"
                   "  b | b" + chr(0) + ".tsv | tsv | k\nearlier:\n  a | plain.txt/old\n"
                   "  b | old" + chr(0) + "\n")
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual((code, err), (2, ""))
        self.assertEqual(out.split("\n"), [
            "DEAD  table a: file missing", "DEAD  table b: cannot be read",
            "DEAD  earlier a: file missing", "DEAD  earlier b: cannot be read",
            "checks: OK 0, FAIL 0, DEAD 4", ""])

    def test_not_utf_8_and_nul(self):
        self.table_reason({"a.tsv": b"k\n" + b"\xff" + b"\n"}, "DEAD  table a: not UTF-8")
        self.table_reason({"a.csv": b"k\n" + b"\xc3" + b"\n"}, "DEAD  table a: not UTF-8",
                          "csv", "a.csv")
        self.table_reason({"a.tsv": b"k\n" + b"\xed\xa0\x80" + b"\n"}, "DEAD  table a: not UTF-8")
        self.table_reason({"a.tsv": b"k\n1\x002\n"}, "DEAD  table a: holds a NUL character")
        self.table_reason({"a.csv": b"k\n1\x002\n"}, "DEAD  table a: holds a NUL character",
                          "csv", "a.csv")
        self.table_reason({"a.tsv": b"\x00"}, "DEAD  table a: holds a NUL character")

    def test_not_utf_8_is_named_before_a_nul_character(self):
        self.table_reason({"a.tsv": b"k\n\xff\x00\n"}, "DEAD  table a: not UTF-8")

    def test_empty_file_and_no_header(self):
        self.table_reason({"a.tsv": b""}, "DEAD  table a: empty file")
        self.table_reason({"a.tsv": b"\xef\xbb\xbf"}, "DEAD  table a: empty file")
        self.table_reason({"a.csv": b""}, "DEAD  table a: empty file", "csv", "a.csv")
        for eol in ("\n", "\r\n", "\r"):
            self.table_reason({"a.tsv": (eol + "k" + eol).encode()}, "DEAD  table a: no header")
            self.table_reason({"a.csv": (eol + "k" + eol).encode()}, "DEAD  table a: no header",
                              "csv", "a.csv")
        self.table_reason({"a.tsv": b"\n"}, "DEAD  table a: no header")

    def test_csv_that_cannot_be_read(self):
        self.table_reason({"a.csv": b'k\n"open\n'}, "DEAD  table a: not readable as CSV",
                          "csv", "a.csv")
        big = 'k\n"' + "x" * 200000 + "\n"
        self.table_reason({"a.csv": big.encode()}, "DEAD  table a: not readable as CSV",
                          "csv", "a.csv")

    def test_a_csv_field_of_any_length_is_read_and_the_field_size_limit_is_put_back(self):
        before = csv.field_size_limit()
        for cell in ("x" * 200000, "x" * 131073 + ",y\n" + "z" * 131073):
            with self.subTest(len(cell)):
                text = 'k,v\n%s,"%s"\n%s,w\n' % (k(1), cell, k(2))
                files = {"a.csv": text}
                code, lines = self.lines("tables:\n  a | a.csv | csv | k\n", files)
                self.assertEqual((code, lines), (0, [
                    "OK    table a: " + base.table_counts(2, 0, 0, 0, 0),
                    "checks: OK 1, FAIL 0, DEAD 0"]))
                self.assertEqual(csv.field_size_limit(), before)

    def test_a_csv_field_of_nine_million_characters_is_read(self):
        before = csv.field_size_limit()
        files = {"a.csv": 'k,v\n%s,"%s"\n' % (k(1), "x" * 9000000)}
        code, lines = self.lines("tables:\n  a | a.csv | csv | k\n", files)
        self.assertEqual((code, lines[0]), (0, "OK    table a: " + base.table_counts(1, 0, 0, 0, 0)))
        self.assertEqual(csv.field_size_limit(), before)

    def test_the_field_size_limit_is_put_back_after_a_csv_that_cannot_be_read(self):
        before = csv.field_size_limit()
        self.table_reason({"a.csv": b'k\n"open\n'}, "DEAD  table a: not readable as CSV",
                          "csv", "a.csv")
        self.assertEqual(csv.field_size_limit(), before)

    def test_a_csv_limit_set_by_another_part_of_the_program_is_not_changed_by_a_run(self):
        before = csv.field_size_limit(5000)
        self.addCleanup(csv.field_size_limit, before)
        files = {"a.csv": "k\n" + "x" * 6000 + "\n"}
        code, lines = self.lines("tables:\n  a | a.csv | csv | k\n", files)
        self.assertEqual(code, 0)
        self.assertEqual(csv.field_size_limit(), 5000)

    def test_a_missing_column_and_a_column_named_twice(self):
        self.table_reason({"a.tsv": tsv([["j"], [k(1)]])}, "DEAD  table a: no column k")
        self.table_reason({"a.tsv": tsv([["k", "k"], [k(1), k(2)]])},
                          "DEAD  table a: column k named twice")
        self.table_reason({"a.tsv": tsv([["K"], [k(1)]])}, "DEAD  table a: no column k")
        self.table_reason({"a.tsv": tsv([[" k"], [k(1)]])}, "DEAD  table a: no column k")

    def test_a_table_with_no_whole_row(self):
        self.table_reason({"a.tsv": tsv([["k", "v"]])}, "DEAD  table a: no whole rows")
        self.table_reason({"a.tsv": "k\tv\n"}, "DEAD  table a: no whole rows")
        self.table_reason({"a.tsv": tsv([["k", "v"], [k(1)], [k(2), "x", "y"]])},
                          "DEAD  table a: no whole rows")
        self.table_reason({"a.csv": "k,v\n\n\n"}, "DEAD  table a: no whole rows",
                          "csv", "a.csv")

    def test_a_column_is_named_before_an_empty_table_is(self):
        self.table_reason({"a.tsv": tsv([["j", "v"]])}, "DEAD  table a: no column k")

    def other(self, key, item, files, line, fmt="tsv"):
        declaration = "tables:\n  a | a.tsv | tsv | k\n  b | b.tsv | tsv | k\n%s:\n  %s\n" % (key, item)
        for extra in (False, True):
            code, lines = self.lines(declaration, files, report_only=extra)
            self.assertEqual(code, 2)
            self.assertIn(line, lines)

    GOOD = {"a.tsv": tsv([["k", "c", "d", "e"], [k(1), k(2), "2026-01-01", ""]]),
            "b.tsv": tsv([["k"], [k(2)]])}

    def test_each_kind_of_check_is_dead_for_a_missing_file_and_a_missing_column(self):
        kinds = [("required", "a | c", "required a.c"), ("values", "a | c | x", "values a.c"),
                 ("dates", "a | d", "dates a.d"), ("corrections", "a | e | d", "corrections a.e")]
        for key, item, label in kinds:
            with self.subTest(key):
                files = dict(self.GOOD)
                del files["a.tsv"]
                self.other(key, item, files, "DEAD  %s: file missing" % label)
                files["a.tsv"] = tsv([["k"], [k(1)]])
                column = item.split(" | ")[1 if key != "corrections" else 1]
                self.other(key, item, files, "DEAD  %s: no column %s" % (label, column))

    def test_a_check_with_a_column_named_twice_is_dead(self):
        files = {"a.tsv": tsv([["k", "c", "c"], [k(1), k(2), k(3)]]), "b.tsv": self.GOOD["b.tsv"]}
        self.other("required", "a | c", files, "DEAD  required a.c: column c named twice")
        self.other("references", "a | c | b | k | single", files,
                   "DEAD  references a.c to b.k: column c named twice")

    def test_a_check_with_no_whole_row_is_dead(self):
        files = {"a.tsv": tsv([["k", "c"]]), "b.tsv": self.GOOD["b.tsv"]}
        self.other("required", "a | c", files, "DEAD  required a.c: no whole rows")
        self.other("values", "a | c | x", files, "DEAD  values a.c: no whole rows")
        self.other("dates", "a | c", files, "DEAD  dates a.c: no whole rows")
        self.other("corrections", "a | c | c", files, "DEAD  corrections a.c: no whole rows")
        self.other("references", "a | c | b | k | single", files,
                   "DEAD  references a.c to b.k: no whole rows")

    def test_a_reference_column_with_no_references_is_dead(self):
        for rule in ("single", "list ,", "pattern [0-9]+"):
            with self.subTest(rule):
                files = {"a.tsv": tsv([["k", "c"], [k(1), ""], [k(2), ""]]), "b.tsv": self.GOOD["b.tsv"]}
                if rule == "list ,":
                    files["a.tsv"] = tsv([["k", "c"], [k(1), " , "], [k(2), ",,"]])
                if rule.startswith("pattern"):
                    files["a.tsv"] = tsv([["k", "c"], [k(1), "none"]])
                self.other("references", "a | c | b | k | " + rule, files,
                           "DEAD  references a.c to b.k: every cell blank")

    def test_values_and_dates_with_only_empty_cells_are_dead(self):
        files = {"a.tsv": tsv([["k", "c"], [k(1), ""], [k(2), ""]]), "b.tsv": self.GOOD["b.tsv"]}
        self.other("values", "a | c | x", files, "DEAD  values a.c: no cell to check")
        self.other("dates", "a | c", files, "DEAD  dates a.c: no cell to check")

    def test_a_corrections_column_with_no_correction_is_dead(self):
        files = {"a.tsv": tsv([["k", "c", "d"], [k(1), "", "2026-01-01"]]),
                 "b.tsv": self.GOOD["b.tsv"]}
        self.other("corrections", "a | c | d", files, "DEAD  corrections a.c: no correction rows")

    def test_a_correction_check_names_the_key_column_then_the_other_two(self):
        files = {"a.tsv": tsv([["j", "c", "d"], [k(1), "", ""]]), "b.tsv": self.GOOD["b.tsv"]}
        self.other("corrections", "a | c | d", files, "DEAD  corrections a.c: no column k")
        files = {"a.tsv": tsv([["k", "x", "y"], [k(1), "", ""]]), "b.tsv": self.GOOD["b.tsv"]}
        self.other("corrections", "a | c | d", files, "DEAD  corrections a.c: no column c")
        files = {"a.tsv": tsv([["k", "c", "y"], [k(1), "", ""]]), "b.tsv": self.GOOD["b.tsv"]}
        self.other("corrections", "a | c | d", files, "DEAD  corrections a.c: no column d")

    def test_a_reference_names_its_own_table_before_the_target(self):
        item = "a | c | b | k | single"
        label = "DEAD  references a.c to b.k: "
        both_missing = {}
        self.other("references", item, both_missing, label + "file missing")
        target_missing = {"a.tsv": self.GOOD["a.tsv"]}
        self.other("references", item, target_missing, label + "target b: file missing")
        target_empty = {"a.tsv": self.GOOD["a.tsv"], "b.tsv": b""}
        self.other("references", item, target_empty, label + "target b: empty file")
        target_nul = {"a.tsv": self.GOOD["a.tsv"], "b.tsv": b"k\n\x00\n"}
        self.other("references", item, target_nul, label + "target b: holds a NUL character")
        both_bad = {"a.tsv": b"", "b.tsv": b"\xff"}
        self.other("references", item, both_bad, label + "empty file")
        target_not_utf = {"a.tsv": self.GOOD["a.tsv"], "b.tsv": b"\xff"}
        self.other("references", item, target_not_utf, label + "target b: not UTF-8")

    def test_a_reference_is_dead_for_a_file_before_a_column_before_a_row(self):
        item = "a | c | b | k | single"
        label = "DEAD  references a.c to b.k: "
        # The target's file is named before the source's missing column.
        files = {"a.tsv": tsv([["x"], ["y"]]), "b.tsv": b""}
        self.other("references", item, files, label + "target b: empty file")
        # The source's column is named before the target's.
        files = {"a.tsv": tsv([["k", "x"], [k(1), k(2)]]), "b.tsv": tsv([["x"], [k(2)]])}
        self.other("references", item, files, label + "no column c")
        # The target's missing column, and a column it names twice, carry the target's name.
        files = {"a.tsv": tsv([["k", "c"], [k(1), k(2)]]), "b.tsv": tsv([["x"], [k(2)]])}
        self.other("references", item, files, label + "target b: no column k")
        files = {"a.tsv": tsv([["k", "c"], [k(1), k(2)]]), "b.tsv": tsv([["k", "k"], [k(2), k(2)]])}
        self.other("references", item, files, label + "target b: column k named twice")
        # Both lack rows: the source's. Only the target: the target's, before any references.
        files = {"a.tsv": tsv([["k", "c"]]), "b.tsv": tsv([["k"]])}
        self.other("references", item, files, label + "no whole rows")
        files = {"a.tsv": tsv([["k", "c"], [k(1), ""]]), "b.tsv": tsv([["k"]])}
        self.other("references", item, files, label + "target b: no whole rows")
        files = {"a.tsv": tsv([["k", "c"], [k(1), ""]]), "b.tsv": tsv([["k"], [k(1), "wide"]])}
        self.other("references", item, files, label + "target b: no whole rows")

    def test_an_earlier_check_with_an_empty_copy_or_no_copy_is_dead(self):
        item = "a | old.tsv"
        label = "DEAD  earlier a: "
        files = dict(self.GOOD)
        self.other("earlier", item, files, label + "earlier copy missing")
        files["old.tsv"] = b""
        self.other("earlier", item, files, label + "earlier copy empty")
        # A copy of only a byte-order mark is not empty: bytes are compared as they are.
        files["old.tsv"] = b"\xef\xbb\xbf"
        code, lines = self.lines("tables:\n  a | a.tsv | tsv | k\nearlier:\n  a | old.tsv\n", files)
        self.assertEqual(section(lines, "earlier a"), [
            "FAIL  earlier a: bytes earlier 3, bytes now %d" % len(self.GOOD["a.tsv"]),
            "a.tsv:1: differs from the earlier copy"])
        folder = self.folder()
        folder.put("a.tsv", self.GOOD["a.tsv"])
        os.mkdir(folder.path("old.tsv"))
        folder.put("record.txt", "tables:\n  a | a.tsv | tsv | k\nearlier:\n  a | old.tsv\n")
        _code, out, _err = self.cli(["record", folder.path("record.txt")])
        self.assertIn(label + "earlier copy not a regular file\n", out)

    def test_an_earlier_copy_that_cannot_be_read_is_dead(self):
        folder = self.folder()
        folder.put("a.tsv", self.GOOD["a.tsv"])
        folder.put("old.tsv", b"k")
        os.chmod(folder.path("old.tsv"), 0)
        self.addCleanup(os.chmod, folder.path("old.tsv"), 0o600)
        if readable_despite_mode_zero(folder.path("old.tsv")):
            self.skipTest("this account reads a file with mode 0")
        folder.put("record.txt", "tables:\n  a | a.tsv | tsv | k\nearlier:\n  a | old.tsv\n")
        code, out, _err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual(code, 2)
        self.assertIn("DEAD  earlier a: earlier copy cannot be read\n", out)

    def test_an_earlier_check_names_the_table_file_before_the_copy(self):
        for files, line in (
                ({}, "DEAD  earlier a: file missing"),
                ({"a.tsv": b"\xff\x00"}, None)):
            declaration = "tables:\n  a | a.tsv | tsv | k\nearlier:\n  a | old.tsv\n"
            code, lines = self.lines(declaration, files)
            if line is not None:
                self.assertIn(line, lines)
        folder = self.folder()
        os.mkdir(folder.path("a.tsv"))
        folder.put("record.txt", "tables:\n  a | a.tsv | tsv | k\nearlier:\n  a | old.tsv\n")
        _code, out, _err = self.cli(["record", folder.path("record.txt")])
        self.assertIn("DEAD  earlier a: not a regular file\n", out)

    def test_a_dead_check_does_not_hide_the_checks_that_ran(self):
        files = {"a.tsv": tsv([["k", "v"], [k(1), "a"], [k(1), "b"]])}
        declaration = TABLES + "required:\n  a | zz\n  a | v\n"
        code, lines = self.lines(declaration, files)
        self.assertEqual(code, 2)
        self.assertEqual([l.split(":")[0] for l in lines if l[:2] in ("OK", "FA", "DE")], [
            "FAIL  table a", "DEAD  required a.zz", "OK    required a.v"])
        self.assertEqual(lines[-1], "checks: OK 1, FAIL 1, DEAD 1")


class SelfTestTest(base.RecordCase):
    def blind(self, original):
        def wrapper(*args, **kwargs):
            outcome = original(*args, **kwargs)
            outcome.findings = []
            return outcome
        return wrapper

    def test_the_built_in_tables_pass(self):
        self.assertIsNone(record_check._self_test())

    def test_a_check_that_finds_nothing_stops_the_run_with_its_kind(self):
        kinds = [("check_table", "table"), ("check_references", "reference"),
                 ("check_required", "required"), ("check_values", "values"),
                 ("check_dates", "dates"), ("check_corrections", "corrections"),
                 ("check_earlier", "earlier")]
        for name, kind in kinds:
            for extra in ([], ["--report-only"]):
                with self.subTest(name=name, extra=extra):
                    patched = unittest.mock.patch.object(
                        record_check, name, self.blind(getattr(record_check, name)))
                    with patched:
                        got = self.cli(["record"] + extra + [KNOWN_DECLARATION])
                    self.assertEqual(got, (2, "", "cannot run: self-test failed: %s\n" % kind))

    def test_a_cell_rule_that_finds_nothing_stops_the_run_with_its_kind(self):
        for name, kind in (("refs_list", "rule list"), ("refs_pattern", "rule pattern"),
                           ("refs_single", "reference")):
            with self.subTest(name):
                with unittest.mock.patch.object(record_check, name, lambda *a: []):
                    got = self.cli(["record", KNOWN_DECLARATION])
                self.assertEqual(got, (2, "", "cannot run: self-test failed: %s\n" % kind))

    def test_a_cell_rule_that_finds_too_much_stops_the_run(self):
        with unittest.mock.patch.object(record_check, "refs_list", lambda cell, chars: [cell]):
            got = self.cli(["record", KNOWN_DECLARATION])
        self.assertEqual(got, (2, "", "cannot run: self-test failed: rule list\n"))

    def test_a_check_that_finds_a_fault_that_is_not_planted_stops_the_run(self):
        def noisy(table, key):
            outcome = record_check.Outcome(None, "x", [(1, "empty key")])
            return outcome
        with unittest.mock.patch.object(record_check, "check_table", noisy):
            got = self.cli(["record", KNOWN_DECLARATION])
        self.assertEqual(got, (2, "", "cannot run: self-test failed: table\n"))

    def test_a_check_with_the_wrong_counts_stops_the_run(self):
        original = record_check.check_dates

        def loose(table, column):
            outcome = original(table, column)
            outcome.counts = outcome.counts.replace("filled 2", "filled 3")
            return outcome
        with unittest.mock.patch.object(record_check, "check_dates", loose):
            got = self.cli(["record", KNOWN_DECLARATION])
        self.assertEqual(got, (2, "", "cannot run: self-test failed: dates\n"))

    def test_the_self_test_runs_before_the_declaration_is_read(self):
        folder = self.folder()
        with unittest.mock.patch.object(record_check, "check_table",
                                        self.blind(record_check.check_table)):
            got = self.cli(["record", folder.path("nothing.txt")])
        self.assertEqual(got, (2, "", "cannot run: self-test failed: table\n"))

    def test_the_self_test_reads_no_file(self):
        real_open = open
        seen = []

        def spy(path, *args, **kwargs):
            seen.append(path)
            return real_open(path, *args, **kwargs)
        with unittest.mock.patch("builtins.open", spy):
            self.assertIsNone(record_check._self_test())
        self.assertEqual(seen, [])


class SentinelAndReadOnlyTest(base.RecordCase):
    def cells(self, folder):
        found = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if name.endswith(".tsv"):
                with open(path, encoding="utf-8", newline="") as handle:
                    rows = [line.split("\t") for line in handle.read().split("\n")[1:] if line]
            elif name.endswith(".csv"):
                with open(path, encoding="utf-8", newline="") as handle:
                    rows = list(csv.reader(handle))[1:]
            else:
                continue
            found.extend(cell for row in rows for cell in row)
        return found

    def test_the_sentinel_fixture_prints_no_cell(self):
        code, out, err = self.cli(["record", os.path.join(SENTINEL_DIR, "record.txt")])
        self.assertEqual((code, err), (1, ""))
        self.assertTrue(out.endswith("checks: OK 2, FAIL 6, DEAD 0\n"))
        self.assertEqual(out.count("\n"), 17)
        self.assertEqual(self.cli(["record", "--report-only",
                                   os.path.join(SENTINEL_DIR, "record.txt")])[0], 0)

    def test_the_sentinel_is_in_every_kind_of_cell_of_the_fixture(self):
        with open(os.path.join(SENTINEL_DIR, "entry-table.tsv"), encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        header = lines[0].split("\t")
        self.assertEqual(header[:5], ["entry", "cites", "grade", "recorded", "corrects"])
        self.assertIn(SENTINEL, header[5])
        rows = [line.split("\t") for line in lines[1:] if line]
        for column in (0, 1, 2, 3, 4, 5):
            self.assertTrue(any(SENTINEL in row[column] for row in rows if len(row) > column), column)
        self.assertTrue(any(len(row) != len(header) and SENTINEL in row[0] for row in rows))

    def test_no_cell_of_three_characters_or_more_is_in_any_output(self):
        outputs = [self.cli(["record", KNOWN_DECLARATION])[1]]
        folder = self.folder()
        for name in os.listdir(KNOWN):
            if name != "entry-table.tsv":
                shutil.copy(os.path.join(KNOWN, name), folder.path(name))
        outputs.append(self.cli(["record", folder.path("record.txt")])[1])
        values = [cell for cell in self.cells(KNOWN) if len(cell) >= 3]
        self.assertGreater(len(values), 15)
        for value in values:
            for out in outputs:
                self.assertNotIn(value, out)

    def snapshot(self, folder):
        found = {}
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            found[name] = (digest, os.stat(path).st_mtime_ns)
        return found

    def test_a_run_changes_no_input_and_creates_nothing(self):
        for fixtures in (KNOWN, SENTINEL_DIR):
            folder = self.folder()
            for name in os.listdir(fixtures):
                shutil.copy2(os.path.join(fixtures, name), folder.path(name))
            before = self.snapshot(folder.dir)
            for extra in ([], ["--report-only"]):
                self.cli(["record"] + extra + [folder.path("record.txt")])
            os.remove(folder.path("origin-table.csv") if fixtures == KNOWN
                      else folder.path("origin-table.csv"))
            gone = self.snapshot(folder.dir)
            self.cli(["record", folder.path("record.txt")])
            self.assertEqual(self.snapshot(folder.dir), gone)
            self.assertEqual(len(gone), len(before) - 1)
            self.assertEqual(len(os.listdir(folder.dir)), len(gone))

    def test_a_run_from_another_folder_writes_nothing_beside_the_declaration(self):
        folder = self.folder()
        for name in os.listdir(KNOWN):
            shutil.copy2(os.path.join(KNOWN, name), folder.path(name))
        before = self.snapshot(folder.dir)
        code, out, err = self.sub(["record", folder.path("record.txt")])
        self.assertEqual(code, 1)
        self.assertEqual(self.snapshot(folder.dir), before)


if __name__ == "__main__":
    unittest.main()
