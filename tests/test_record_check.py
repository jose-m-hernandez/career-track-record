"""Tests for ``track-record record``. Every table, declaration and value here is invented.

The known answer is the spec's section 9 example, read from the spec file itself. The
sentinel ``zq-sentinel-7`` is planted in cells throughout; ``RecordCase.tearDown`` finds it in
neither stream of any run a test made, and finds no traceback in either. Invisible and control
characters are written with chr(), never raw.
"""

import csv
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
KNOWN = os.path.join(ROOT, "tests", "fixtures", "record", "known")
SPEC = os.path.join(ROOT, "docs", "specs", "record-check.md")
CMD = [sys.executable, "-m", "career_track_record"]

sys.path.insert(0, SRC)

from career_track_record import cli, record_check  # noqa: E402

SENTINEL = "zq-sentinel-7"
FENCE = "`" * 3
NO_OUTPUT = "cannot run: cannot write output\n"


def k(number):
    """An invented cell value that carries the sentinel."""
    return "%s-%02d" % (SENTINEL, number)


def tsv(rows, eol="\n", final=True):
    text = eol.join("\t".join(row) for row in rows)
    return text + (eol if final else "")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def fenced_after(text, marker):
    """The first fenced block that follows ``marker`` in ``text``, with a final line break."""
    start = text.index(marker)
    first = text.index(FENCE, start)
    first = text.index("\n", first) + 1
    last = text.index(FENCE, first)
    return text[first:last]


def counts_line(e, w, r, x, y, z):
    return ("whole rows %d, blank %d, references %d, dangling %d, "
            "rows with dangling %d, distinct dangling %d" % (e, w, r, x, y, z))


def table_counts(e, n, k_, d, u):
    return ("whole rows %d, ragged rows %d, empty keys %d, repeats %d, keys with repeats %d"
            % (e, n, k_, d, u))


def env():
    e = dict(os.environ)
    e["PYTHONPATH"] = SRC
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


class Folder(object):
    def __init__(self, path):
        self.dir = path

    def path(self, name):
        return os.path.join(self.dir, name)

    def put(self, name, content):
        if isinstance(content, str):
            content = content.encode("utf-8")
        with open(self.path(name), "wb") as handle:
            handle.write(content)


class RecordCase(unittest.TestCase):
    def setUp(self):
        self.captured = []

    def tearDown(self):
        for args, out, err in self.captured:
            for name, text in (("stdout", out), ("stderr", err)):
                self.assertNotIn(SENTINEL, text, "the sentinel is in %s of %r" % (name, args))
                self.assertNotIn("Traceback", text, "a traceback in %s of %r" % (name, args))

    def folder(self):
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path, True)
        return Folder(path)

    def cli(self, args):
        """Run the command in this process: (exit status, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(sys, "stdout", out), \
                unittest.mock.patch.object(sys, "stderr", err):
            code = cli.main(list(args))
        self.captured.append((list(args), out.getvalue(), err.getvalue()))
        return code, out.getvalue(), err.getvalue()

    def sub(self, args, timeout=30, shell_tail=""):
        """Run the command in its own process, as a user does."""
        if shell_tail:
            command = ["/bin/sh", "-c", 'exec "$0" "$@" ' + shell_tail] + CMD + list(args)
        else:
            command = CMD + list(args)
        p = subprocess.run(command, env=env(), stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out, err = p.stdout.decode("utf-8"), p.stderr.decode("utf-8")
        self.captured.append((list(args), out, err))
        return p.returncode, out, err

    def go(self, declaration, files, report_only=False, name="record.txt"):
        folder = self.folder()
        for file_name, content in files.items():
            folder.put(file_name, content)
        folder.put(name, declaration)
        args = ["record"] + (["--report-only"] if report_only else []) + [folder.path(name)]
        return self.cli(args)

    def lines(self, declaration, files, report_only=False):
        code, out, err = self.go(declaration, files, report_only)
        self.assertEqual(err, "")
        self.assertTrue(out.endswith("\n"))
        return code, out[:-1].split("\n")


def ref_declaration(rule, source="a.tsv", fmt="tsv"):
    return ("tables:\n  a | %s | %s | k\n  b | b.tsv | tsv | k\nreferences:\n"
            "  a | c | b | k | %s\n" % (source, fmt, rule))


TARGET = tsv([["k"], [k(1)], [k(2)], [k(3)]])


def one_reference(rows, rule="single", target=TARGET):
    """The status line and findings of a reference check over ``rows`` (header k, c)."""
    return {"a.tsv": tsv([["k", "c"]] + rows), "b.tsv": target}, ref_declaration(rule)


class KnownAnswerTest(RecordCase):
    def spec_output(self):
        return fenced_after(read(SPEC), "`<cli> record record.txt` writes:")

    def test_the_known_run_equals_the_spec_block_and_exits_1(self):
        code, out, err = self.cli(["record", os.path.join(KNOWN, "record.txt")])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, self.spec_output())
        self.assertTrue(out.endswith("checks: OK 2, FAIL 6, DEAD 0\n"))

    def test_report_only_exits_0_with_the_same_output(self):
        code, out, err = self.cli(["record", "--report-only", os.path.join(KNOWN, "record.txt")])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, self.spec_output())

    def test_the_fixtures_are_the_spec_example(self):
        spec = read(SPEC)
        for name, marker in (("entry-table.tsv", "`entry-table.tsv`, with"),
                             ("origin-table.csv", "`origin-table.csv`:")):
            block = fenced_after(spec, marker)
            if name.endswith(".tsv"):
                block = block.replace(chr(0x2192), "\t")
            self.assertEqual(read(os.path.join(KNOWN, name)), block, name)
        with open(os.path.join(KNOWN, "entry-table.tsv"), encoding="utf-8") as handle:
            first_three = "".join(handle.readlines()[:3])
        self.assertEqual(read(os.path.join(KNOWN, "entry-table-before.tsv")), first_three)
        self.assertEqual(read(os.path.join(KNOWN, "record.txt")),
                         fenced_after(spec, "An invented declaration, `record.txt`:"))

    def test_the_missing_table_makes_every_check_on_it_dead_and_exits_2(self):
        folder = self.folder()
        for name in os.listdir(KNOWN):
            if name != "entry-table.tsv":
                shutil.copy(os.path.join(KNOWN, name), folder.path(name))
        want = "\n".join([
            "DEAD  table entries: file missing",
            "OK    table origins: " + table_counts(2, 0, 0, 0, 0),
            "DEAD  references entries.cites to origins.origin: file missing",
            "DEAD  required entries.grade: file missing",
            "DEAD  values entries.grade: file missing",
            "DEAD  dates entries.recorded: file missing",
            "DEAD  corrections entries.corrects: file missing",
            "DEAD  earlier entries: file missing",
            "checks: OK 1, FAIL 0, DEAD 7", ""])
        for extra in ([], ["--report-only"]):
            code, out, err = self.cli(["record"] + extra + [folder.path("record.txt")])
            self.assertEqual((code, out, err), (2, want, ""))


class HelpTest(RecordCase):
    def test_help_equals_the_spec_block(self):
        want = fenced_after(read(SPEC), "`<cli> record --help` writes exactly this")
        self.assertEqual(self.cli(["record", "--help"]), (0, want, ""))
        self.assertEqual(self.cli(["record", "-h"]), (0, want, ""))

    def test_help_wins_over_every_other_argument_and_reads_no_file(self):
        want = fenced_after(read(SPEC), "`<cli> record --help` writes exactly this")
        for args in (["a", "b", "-h"], ["--bogus", "--help"], ["--report-only=x", "-h"],
                     ["--report-only", "nothing-here.txt", "--help"]):
            with self.subTest(args):
                self.assertEqual(self.cli(["record"] + args), (0, want, ""))

    def test_after_two_dashes_help_is_a_file_name(self):
        code, out, err = self.cli(["record", "--", "-h"])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "cannot run: cannot read the declaration: -h\n")

    def test_the_top_level_help_lists_record(self):
        code, out, err = self.sub(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("    record    check your record's tables against rules you declare", out)

    def test_a_dash_alone_is_a_file_name_not_standard_input(self):
        code, out, err = self.cli(["record", "-"])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "cannot run: cannot read the declaration: -\n")


class CellRuleTest(RecordCase):
    def test_single_is_exact_and_case_sensitive(self):
        files, declaration = one_reference([
            [k(10), k(1)], [k(11), " " + k(1)], [k(12), k(1).upper()], [k(13), ""]])
        code, lines = self.lines(declaration, files)
        self.assertEqual(code, 1)
        self.assertEqual(lines[2:5], [
            "FAIL  references a.c to b.k: " + counts_line(4, 1, 3, 2, 2, 2),
            "a.tsv:3: dangling 1", "a.tsv:4: dangling 1"])

    def test_single_does_not_split_a_cell(self):
        files, declaration = one_reference([[k(10), k(1) + "," + k(2)]])
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2], "FAIL  references a.c to b.k: " + counts_line(1, 0, 1, 1, 1, 1))

    def test_list_splits_at_each_of_two_separators_trims_spaces_and_drops_empty_parts(self):
        files, declaration = one_reference([
            [k(10), "%s,%s;%s" % (k(1), k(2), k(9))],
            [k(11), ",, %s ," % k(3)],
            [k(12), " , ;"]], rule="list ,;")
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2:4], [
            "FAIL  references a.c to b.k: " + counts_line(3, 1, 4, 1, 1, 1),
            "a.tsv:2: dangling 1"])

    def test_list_separator_set_is_exactly_the_characters_given(self):
        files, declaration = one_reference([[k(10), "%s;%s" % (k(1), k(2))]], rule="list ,")
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2], "FAIL  references a.c to b.k: " + counts_line(1, 0, 1, 1, 1, 1))

    def test_list_trims_plain_spaces_only_so_a_tab_stays(self):
        cell = "\t%s , %s" % (k(1), k(2))
        files = {"a.csv": "k,c\n%s,\"%s\"\n" % (k(10), cell), "b.tsv": TARGET}
        declaration = ref_declaration("list ,", source="a.csv", fmt="csv")
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2:4], [
            "FAIL  references a.c to b.k: " + counts_line(1, 0, 2, 1, 1, 1),
            "a.csv:2: dangling 1"])

    def test_list_with_nothing_left_holds_no_reference(self):
        files, declaration = one_reference([[k(10), " , ,"], [k(11), k(1)]], rule="list ,")
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2], "OK    references a.c to b.k: " + counts_line(2, 1, 1, 0, 0, 0))

    def test_pattern_takes_every_match_without_overlap(self):
        files, declaration = one_reference([
            [k(10), "see %s and %s, %s" % (k(1), k(2), k(99))],
            [k(11), k(3) + k(1)],
            [k(12), "none here"]], rule="pattern %s-[0-9]+" % SENTINEL)
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2:4], [
            "FAIL  references a.c to b.k: " + counts_line(3, 1, 5, 1, 1, 1),
            "a.tsv:2: dangling 1"])

    def test_pattern_skips_an_empty_match(self):
        files, declaration = one_reference(
            [[k(10), "ab12cd"], [k(11), "x7y7"], [k(12), "abc"]], rule="pattern [0-9]*",
            target=tsv([["k"], ["12"]]))
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2:4], [
            "FAIL  references a.c to b.k: " + counts_line(3, 1, 3, 2, 1, 1),
            "a.tsv:3: dangling 2"])

    def test_a_reference_label_shows_both_columns_escaped(self):
        esc = chr(0x1b)
        files = {"a.tsv": tsv([["k", "c" + esc], [k(10), k(1)]]),
                 "b.csv": "k,\"k%s\"\n%s,%s\n" % (esc, k(5), k(1))}
        declaration = ("tables:\n  a | a.tsv | tsv | k\n  b | b.csv | csv | k\nreferences:\n"
                       "  a | c%s | b | k%s | single\n" % (esc, esc))
        _code, out, _err = self.go(declaration, files)
        self.assertNotIn(esc, out)
        self.assertIn("OK    references a.c\\x1b to b.k\\x1b: " + counts_line(1, 0, 1, 0, 0, 0)
                      + "\n", out)

    def test_a_pattern_is_case_sensitive(self):
        files, declaration = one_reference(
            [[k(10), "O-01 o-02"]], rule="pattern o-[0-9]+",
            target=tsv([["k"], ["o-02"], ["O-01"]]))
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2], "OK    references a.c to b.k: " + counts_line(1, 0, 1, 0, 0, 0))

    def test_the_counts_tell_references_rows_and_distinct_apart(self):
        files, declaration = one_reference([
            [k(10), "%s,%s" % (k(9), k(9))], [k(11), k(9)], [k(12), "%s,%s" % (k(8), k(1))]],
            rule="list ,")
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2], "FAIL  references a.c to b.k: " + counts_line(3, 0, 5, 4, 3, 2))

    def test_a_ragged_row_is_neither_a_source_nor_a_target(self):
        files = {"a.tsv": tsv([["k", "c"], [k(10), k(1)], [k(11), k(7), "extra"], [k(12)]]),
                 "b.tsv": tsv([["k"], [k(1)], [k(7), "extra"]])}
        _code, lines = self.lines(ref_declaration("single"), files)
        self.assertEqual(section(lines, "table a")[0], "FAIL  table a: " + table_counts(1, 2, 0, 0, 0))
        self.assertEqual(section(lines, "table b")[0], "FAIL  table b: " + table_counts(1, 1, 0, 0, 0))
        self.assertEqual(section(lines, "references a.c to b.k"),
                         ["OK    references a.c to b.k: " + counts_line(1, 0, 1, 0, 0, 0)])

    def test_a_ragged_target_row_does_not_resolve_a_reference(self):
        files = {"a.tsv": tsv([["k", "c"], [k(10), k(7)]]),
                 "b.tsv": tsv([["k"], [k(1)], [k(7), "extra"]])}
        _code, lines = self.lines(ref_declaration("single"), files)
        self.assertEqual(section(lines, "references a.c to b.k")[0],
                         "FAIL  references a.c to b.k: " + counts_line(1, 0, 1, 1, 1, 1))

    # Known limit: a name that holds " | " cannot be declared, because the declaration splits
    # each item at that text. A list separator cannot be a space, because spaces are trimmed.
    def test_a_pipe_can_be_a_list_separator(self):
        files, declaration = one_reference([[k(10), "%s|%s" % (k(1), k(2))]], rule="list |")
        _code, lines = self.lines(declaration, files)
        self.assertEqual(lines[2], "OK    references a.c to b.k: " + counts_line(1, 0, 2, 0, 0, 0))


class TableCheckTest(RecordCase):
    def one(self, text, fmt="tsv", name="t.tsv"):
        declaration = "tables:\n  t | %s | %s | k\n" % (name, fmt)
        code, lines = self.lines(declaration, {name: text})
        return code, lines

    def test_repeats_and_keys_with_repeats_count_different_things(self):
        rows = [["k", "v"], [k(1), "a"], [k(1), "b"], [k(1), "c"], [k(2), "d"], [k(2), "e"],
                [k(3), "f"]]
        code, lines = self.one(tsv(rows))
        self.assertEqual(code, 1)
        self.assertEqual(lines, [
            "FAIL  table t: " + table_counts(6, 0, 0, 3, 2),
            "t.tsv:3: repeated key, first on line 2", "t.tsv:4: repeated key, first on line 2",
            "t.tsv:6: repeated key, first on line 5",
            "checks: OK 0, FAIL 1, DEAD 0"])

    def test_an_empty_key_is_a_fault_and_is_not_a_repeat_of_another_empty_key(self):
        code, lines = self.one(tsv([["k", "v"], ["", "a"], ["", "b"], [k(1), "c"]]))
        self.assertEqual(lines[:3], [
            "FAIL  table t: " + table_counts(3, 0, 2, 0, 0), "t.tsv:2: empty key",
            "t.tsv:3: empty key"])

    def test_findings_come_in_file_order_across_the_three_kinds(self):
        text = tsv([["k", "v"], [k(1), "a"], [k(2)], [k(1), "b"], ["", "c"], [k(3), "d", "e"]])
        _code, lines = self.one(text)
        self.assertEqual(lines, [
            "FAIL  table t: " + table_counts(3, 2, 1, 1, 1),
            "t.tsv:3: fields 1, the header has 2", "t.tsv:4: repeated key, first on line 2",
            "t.tsv:5: empty key", "t.tsv:6: fields 3, the header has 2",
            "checks: OK 0, FAIL 1, DEAD 0"])

    def test_a_key_on_a_ragged_row_is_not_a_first_occurrence(self):
        text = tsv([["k", "v"], [k(1)], [k(1), "a"], [k(1), "b"]])
        _code, lines = self.one(text)
        self.assertEqual(lines[1:4], [
            "t.tsv:2: fields 1, the header has 2", "t.tsv:4: repeated key, first on line 3",
            "checks: OK 0, FAIL 1, DEAD 0"])

    def test_a_clean_table_is_ok(self):
        code, lines = self.one(tsv([["k", "v"], [k(1), "a"], [k(2), "b"]]))
        self.assertEqual((code, lines[0]), (0, "OK    table t: " + table_counts(2, 0, 0, 0, 0)))

    def test_a_byte_order_mark_is_not_part_of_the_first_column_name(self):
        for fmt, name, text in (("tsv", "t.tsv", tsv([["k", "v"], [k(1), "a"]])),
                                ("csv", "t.csv", "k,v\n%s,a\n" % k(1))):
            with self.subTest(fmt):
                folder = self.folder()
                folder.put(name, b"\xef\xbb\xbf" + text.encode("utf-8"))
                folder.put("record.txt", "tables:\n  t | %s | %s | k\n" % (name, fmt))
                code, out, err = self.cli(["record", folder.path("record.txt")])
                self.assertEqual((code, out.split("\n")[0], err),
                                 (0, "OK    table t: " + table_counts(1, 0, 0, 0, 0), ""))

    def test_crlf_and_a_lone_cr_end_lines_like_lf(self):
        rows = [["k", "v"], [k(1), "a"], [k(1), "b"], [k(2)]]
        want = None
        for eol in ("\n", "\r\n", "\r"):
            for final in (True, False):
                with self.subTest(eol=repr(eol), final=final):
                    code, lines = self.one(tsv(rows, eol, final))
                    self.assertEqual(code, 1)
                    self.assertEqual(lines[1:3], [
                        "t.tsv:3: repeated key, first on line 2",
                        "t.tsv:4: fields 1, the header has 2"])

    def test_a_final_line_break_does_not_start_a_row(self):
        _code, lines = self.one("k\tv\n%s\ta\n" % k(1))
        self.assertEqual(lines[0], "OK    table t: " + table_counts(1, 0, 0, 0, 0))

    def test_an_empty_line_is_skipped_but_still_numbered(self):
        _code, lines = self.one("k\tv\n\n%s\ta\n\n%s\ta\n" % (k(1), k(1)))
        self.assertEqual(lines[1], "t.tsv:5: repeated key, first on line 3")

    def test_a_line_of_spaces_is_a_row_with_a_key(self):
        _code, lines = self.one("k\n \n \n")
        self.assertEqual(lines[:2], ["FAIL  table t: " + table_counts(2, 0, 0, 1, 1),
                                     "t.tsv:3: repeated key, first on line 2"])

    def test_a_csv_field_may_hold_a_comma(self):
        text = 'k,v\n%s,"a,b"\n%s,"c,d"\n' % (k(1), k(1))
        _code, lines = self.one(text, "csv", "t.csv")
        self.assertEqual(lines[:2], [
            "FAIL  table t: " + table_counts(2, 0, 0, 1, 1),
            "t.csv:3: repeated key, first on line 2"])

    def test_a_csv_field_may_hold_a_line_break_and_the_next_row_starts_after_it(self):
        text = 'k,v\n%s,"line one\nline two"\n%s,x\n%s,y\n' % (k(1), k(2), k(2))
        _code, lines = self.one(text, "csv", "t.csv")
        self.assertEqual(lines[:2], [
            "FAIL  table t: " + table_counts(3, 0, 0, 1, 1),
            "t.csv:5: repeated key, first on line 4"])

    def test_csv_lines_end_at_crlf_and_at_a_lone_cr(self):
        for eol in ("\r\n", "\r"):
            with self.subTest(eol=repr(eol)):
                text = eol.join(["k,v", k(1) + ",a", k(1) + ",b", ""])
                _code, lines = self.one(text, "csv", "t.csv")
                self.assertEqual(lines[1], "t.csv:3: repeated key, first on line 2")

    def test_csv_quotes_are_read_strictly(self):
        for text in ('k,v\n%s,"unterminated\n' % k(1), 'k,v\n%s,"a"b\n' % k(1),
                     '"k,v\n%s,a\n' % k(1)):
            with self.subTest(text[:12]):
                code, lines = self.one(text, "csv", "t.csv")
                self.assertEqual((code, lines[0]), (2, "DEAD  table t: not readable as CSV"))

    def test_a_blank_csv_line_is_skipped_but_numbered(self):
        _code, lines = self.one("k,v\n\n%s,a\n%s,b\n" % (k(1), k(1)), "csv", "t.csv")
        self.assertEqual(lines[1], "t.csv:4: repeated key, first on line 3")

    def test_the_earlier_check_counts_a_lone_cr_as_a_line_break(self):
        files = {"t.tsv": "k\rv\rx\r", "t.old": "k\rv\rw\r"}
        declaration = "tables:\n  t | t.tsv | tsv | k\nearlier:\n  t | t.old\n"
        _code, lines = self.lines(declaration, files)
        self.assertEqual(section(lines, "earlier t"), [
            "FAIL  earlier t: bytes earlier 6, bytes now 6", "t.tsv:3: differs from the earlier copy"])


def section(lines, label):
    """The status line of the check labelled ``label`` and the finding lines under it."""
    status = re.compile(r"(OK  |FAIL|DEAD)  ")
    for i, line in enumerate(lines):
        if status.match(line) and line[6:].startswith(label + ":"):
            j = i + 1
            while j < len(lines) and not status.match(lines[j]) and not lines[j].startswith("checks:"):
                j += 1
            return lines[i:j]
    raise AssertionError("no check labelled %s in %r" % (label, lines))


class CheckKindTest(RecordCase):
    def run_one(self, key, item, text, label):
        declaration = "tables:\n  t | t.tsv | tsv | k\n%s:\n  %s\n" % (key, item)
        code, lines = self.lines(declaration, {"t.tsv": text})
        return code, section(lines, label)

    def test_required_reports_an_empty_cell_and_not_a_cell_of_spaces(self):
        text = tsv([["k", "g"], [k(1), ""], [k(2), " "], [k(3), "A"]])
        code, found = self.run_one("required", "t | g", text, "required t.g")
        self.assertEqual(code, 1)
        self.assertEqual(found, ["FAIL  required t.g: whole rows 3, empty 1", "t.tsv:2: empty"])

    def test_values_checks_only_a_non_empty_cell_and_compares_exactly(self):
        text = tsv([["k", "g"], [k(1), "A"], [k(2), "a"], [k(3), ""], [k(4), "A "], [k(5), "B"]])
        _code, found = self.run_one("values", "t | g | A | B", text, "values t.g")
        self.assertEqual(found, [
            "FAIL  values t.g: whole rows 5, filled 4, outside the set 2",
            "t.tsv:3: outside the set", "t.tsv:5: outside the set"])

    def test_values_may_name_one_value_and_a_value_may_hold_spaces(self):
        text = tsv([["k", "g"], [k(1), "two words"]])
        _code, found = self.run_one("values", "t | g | two words", text, "values t.g")
        self.assertEqual(found, ["OK    values t.g: whole rows 1, filled 1, outside the set 0"])

    def test_dates_accepts_only_real_calendar_dates_written_year_month_day(self):
        good = ["2026-01-05", "2024-02-29"]
        bad = ["2026-02-30", "2025-02-29", "2026-13-01", "2026-00-10", "2026-1-5", "26-01-05", "2026-2-3", "2026-02-3", "2026-2-03", "026-02-03",
               "2026/01/05", "2026-01-05 ", " 2026-01-05", "0000-01-01", "2026-01-05T00",
               chr(0x0662) + "026-01-05", "2026-01-32"]
        rows = [["k", "d"]] + [[k(i), cell] for i, cell in enumerate(good + bad)]
        _code, found = self.run_one("dates", "t | d", tsv(rows), "dates t.d")
        self.assertEqual(found[0], "FAIL  dates t.d: whole rows %d, filled %d, not a date %d"
                         % (len(rows) - 1, len(rows) - 1, len(bad)))
        self.assertEqual(found[1:], ["t.tsv:%d: not a date" % (n + 2 + len(good))
                                     for n in range(len(bad))])

    def test_dates_ignores_an_empty_cell(self):
        text = tsv([["k", "d"], [k(1), ""], [k(2), "2026-01-05"]])
        _code, found = self.run_one("dates", "t | d", text, "dates t.d")
        self.assertEqual(found, ["OK    dates t.d: whole rows 2, filled 1, not a date 0"])

    def corrections(self, rows):
        text = tsv([["k", "c", "d"]] + rows)
        return self.run_one("corrections", "t | c | d", text, "corrections t.c")

    def test_each_correction_fault_has_its_wording(self):
        cases = [
            ("corrects itself", [[k(1), "", "2026-01-01"], [k(2), k(2), "2026-01-02"]],
             "t.tsv:3: corrects itself"),
            ("corrects a missing row", [[k(1), "", "2026-01-01"], [k(2), k(9), "2026-01-02"]],
             "t.tsv:3: corrects a missing row"),
            ("not unique", [[k(1), "", "2026-01-01"], [k(1), "", "2026-01-02"],
                            [k(3), k(1), "2026-01-03"]],
             "t.tsv:4: corrects a key that is not unique"),
            ("later", [[k(1), k(2), "2026-01-01"], [k(2), "", "2026-01-02"]],
             "t.tsv:2: corrects a later row, line 3"),
            ("dates cannot be compared (correction)",
             [[k(1), "", "2026-01-01"], [k(2), k(1), "soon"]],
             "t.tsv:3: dates cannot be compared, line 2"),
            ("dates cannot be compared (corrected row)",
             [[k(1), "", ""], [k(2), k(1), "2026-01-02"]],
             "t.tsv:3: dates cannot be compared, line 2"),
            ("dated before", [[k(1), "", "2026-01-05"], [k(2), k(1), "2026-01-04"]],
             "t.tsv:3: dated before the row it corrects, line 2"),
        ]
        for label, rows, finding in cases:
            with self.subTest(label):
                code, found = self.corrections(rows)
                self.assertEqual(code, 1)
                self.assertEqual(found, ["FAIL  corrections t.c: whole rows %d, corrections 1, "
                                         "faults 1" % len(rows), finding])

    def test_the_same_date_is_not_a_fault_and_a_later_date_is_not_either(self):
        code, found = self.corrections([
            [k(1), "", "2026-01-05"], [k(2), k(1), "2026-01-05"], [k(3), k(2), "2026-02-01"]])
        self.assertEqual(found, ["OK    corrections t.c: whole rows 3, corrections 2, faults 0"])

    def test_the_first_fault_that_applies_is_the_only_one_reported(self):
        # Row 4 corrects itself and also repeats a key and has a bad date: itself wins.
        _code, found = self.corrections([[k(1), "", "x"], [k(2), "", "x"], [k(2), k(2), "x"]])
        self.assertEqual(found, [
            "FAIL  corrections t.c: whole rows 3, corrections 1, faults 1", "t.tsv:4: corrects itself"])
        # A missing key is named before a later row can be; not unique before a later row;
        # a later row before the dates are read.
        _code, found = self.corrections([[k(1), k(1) + "x", "x"], [k(2), "", "x"]])
        self.assertEqual(found[1], "t.tsv:2: corrects a missing row")
        _code, found = self.corrections([[k(1), k(2), "x"], [k(2), "", "x"], [k(2), "", "x"]])
        self.assertEqual(found[1], "t.tsv:2: corrects a key that is not unique")
        _code, found = self.corrections([[k(1), k(2), "x"], [k(2), "", "y"]])
        self.assertEqual(found[1], "t.tsv:2: corrects a later row, line 3")

    def test_a_correction_of_a_ragged_row_names_its_line(self):
        code, found = self.corrections([
            [k(1), "", "2026-01-01"], [k(2), k(9), "2026-01-02"], [k(9)]])
        self.assertEqual(code, 1)
        self.assertEqual(found, ["FAIL  corrections t.c: whole rows 2, corrections 1, faults 1",
                                 "t.tsv:3: corrects a ragged row, line 4"])

    def test_the_first_ragged_row_is_named_and_a_key_on_no_row_is_still_missing(self):
        _code, found = self.corrections([
            [k(1), "", "2026-01-01"], [k(2), k(9), "2026-01-02"], [k(9), "x"], [k(9)],
            [k(3), k(8), "2026-01-03"]])
        self.assertEqual(found, [
            "FAIL  corrections t.c: whole rows 3, corrections 2, faults 2",
            "t.tsv:3: corrects a ragged row, line 4", "t.tsv:6: corrects a missing row"])

    def test_a_ragged_row_holds_a_key_only_where_the_key_column_stands(self):
        # The key column is the first; a ragged row that holds the key in its second field
        # does not hold it where the key column stands.
        _code, found = self.corrections([
            [k(1), "", "2026-01-01"], [k(2), k(9), "2026-01-02"], [k(8), k(9)]])
        self.assertEqual(found[1], "t.tsv:3: corrects a missing row")

    def test_a_ragged_row_too_short_to_reach_the_key_column_holds_no_key(self):
        # The key is the third column; a ragged row of one or two fields does not reach it.
        text = tsv([["c", "d", "k"], ["", "2026-01-01", k(1)], [k(9), "2026-01-02", k(2)],
                    [k(9)], [k(9), "x"], [k(9), "x", k(8), "y"]])
        declaration = "tables:\n  t | t.tsv | tsv | k\ncorrections:\n  t | c | d\n"
        _code, lines = self.lines(declaration, {"t.tsv": text})
        self.assertEqual(section(lines, "corrections t.c"), [
            "FAIL  corrections t.c: whole rows 2, corrections 1, faults 1",
            "t.tsv:3: corrects a missing row"])
        text = tsv([["c", "d", "k"], ["", "2026-01-01", k(1)], [k(8), "2026-01-02", k(2)],
                    [k(9)], [k(9), "x", k(8), "y"]])
        _code, lines = self.lines(declaration, {"t.tsv": text})
        self.assertEqual(section(lines, "corrections t.c")[1:],
                         ["t.tsv:3: corrects a ragged row, line 5"])

    def test_a_correction_may_point_at_the_row_before_it(self):
        _code, found = self.corrections([[k(1), "", "2026-01-05"], [k(2), k(1), "2026-01-06"]])
        self.assertEqual(found, ["OK    corrections t.c: whole rows 2, corrections 1, faults 0"])

    def earlier(self, now, old, name="t.tsv"):
        folder = self.folder()
        folder.put(name, now)
        folder.put("old.tsv", old)
        folder.put("record.txt", "tables:\n  t | %s | tsv | k\nearlier:\n  t | old.tsv\n" % name)
        code, out, err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual(err, "")
        return section(out[:-1].split("\n"), "earlier t")

    def test_an_earlier_copy_that_is_the_start_of_the_file_is_ok(self):
        now = tsv([["k", "v"], [k(1), "a"], [k(2), "b"]])
        old = tsv([["k", "v"], [k(1), "a"]])
        for copy, label in ((old, "a prefix"), (now, "the whole file")):
            with self.subTest(label):
                found = self.earlier(now.encode("utf-8"), copy.encode("utf-8"))
                self.assertEqual(found, ["OK    earlier t: bytes earlier %d, bytes now %d"
                                         % (len(copy), len(now))])

    def test_a_file_shorter_than_its_earlier_copy_is_named_without_a_line(self):
        found = self.earlier(b"k\tv\n", b"k\tv\n1\t2\n")
        self.assertEqual(found, ["FAIL  earlier t: bytes earlier 8, bytes now 4",
                                 "t.tsv: shorter than the earlier copy"])

    def test_a_difference_within_the_common_length_wins_over_shorter(self):
        found = self.earlier(b"X\tv\n", b"k\tv\n1\t2\n")
        self.assertEqual(found[1], "t.tsv:1: differs from the earlier copy")
        found = self.earlier(b"k\tv\n1\t3", b"k\tv\n1\t2\n4")
        self.assertEqual(found[1], "t.tsv:2: differs from the earlier copy")

    def test_only_a_strict_prefix_of_the_earlier_copy_is_shorter(self):
        found = self.earlier(b"k\tv\n1", b"k\tv\n1\t2\n")
        self.assertEqual(found, ["FAIL  earlier t: bytes earlier 8, bytes now 5",
                                 "t.tsv: shorter than the earlier copy"])

    def test_an_lf_file_against_a_crlf_earlier_copy_differs_at_the_first_byte_that_does(self):
        found = self.earlier(b"k\tv\n1\t2\n", b"k\tv\r\n1\t2\r\n")
        self.assertEqual(found, ["FAIL  earlier t: bytes earlier 10, bytes now 8",
                                 "t.tsv:1: differs from the earlier copy"])

    def test_a_cr_only_file_names_the_line_where_it_differs(self):
        found = self.earlier(b"a\rb\rc\rd\r", b"a\rb\rX\rd\r")
        self.assertEqual(found[1], "t.tsv:3: differs from the earlier copy")

    def test_a_crlf_pair_is_one_line_break_when_the_file_differs_after_it(self):
        found = self.earlier(b"a\r\nb\r\nc\n", b"a\r\nb\r\nd\n")
        self.assertEqual(found[1], "t.tsv:3: differs from the earlier copy")

    def test_an_earlier_copy_that_is_the_table_file_itself_is_dead(self):
        folder = self.folder()
        folder.put("t.tsv", tsv([["k"], [k(1)]]))
        os.symlink(folder.path("t.tsv"), folder.path("link.tsv"))
        for name in ("t.tsv", "link.tsv", "./t.tsv"):
            with self.subTest(name):
                folder.put("record.txt",
                           "tables:\n  t | t.tsv | tsv | k\nearlier:\n  t | %s\n" % name)
                code, out, err = self.cli(["record", folder.path("record.txt")])
                self.assertEqual((code, err), (2, ""))
                self.assertEqual(section(out[:-1].split("\n"), "earlier t"),
                                 ["DEAD  earlier t: earlier copy is the table file itself"])

    def test_a_copy_of_the_table_file_is_not_the_table_file_itself(self):
        folder = self.folder()
        folder.put("t.tsv", tsv([["k"], [k(1)]]))
        shutil.copy(folder.path("t.tsv"), folder.path("copy.tsv"))
        folder.put("record.txt", "tables:\n  t | t.tsv | tsv | k\nearlier:\n  t | copy.tsv\n")
        code, out, _err = self.cli(["record", folder.path("record.txt")])
        self.assertEqual(code, 0)
        self.assertIn("OK    earlier t: ", out)

    def test_the_first_differing_byte_names_its_line(self):
        cases = [(b"x\nb\nc\n", b"a\nb\n", 1), (b"a\nb\nc\n", b"a\nB\n", 2),
                 (b"a\nb\nc\n", b"a\nb\nd", 3), (b"a\nb\nC\n", b"a\nb\nc\n", 3),
                 (b"a\nb\r\nc\n", b"a\nb\r\nd\n", 3), (b"ab\n\n\nz", b"ab\n\n\ny", 4),
                 (b"a\n\nz", b"a\nXz", 2), (b"\nz", b"Xz", 1)]
        for now, old, line in cases:
            with self.subTest(now=now, old=old):
                found = self.earlier(now, old)
                self.assertEqual(found[1], "t.tsv:%d: differs from the earlier copy" % line)

    def test_an_earlier_check_needs_no_header_and_reads_the_file_as_bytes(self):
        self.assertEqual(self.earlier(b"\nabc\n", b"\nab"),
                         ["OK    earlier t: bytes earlier 3, bytes now 5"])
        self.assertEqual(self.earlier(b"\xff\xfe\x00z\n", b"\xff\xfe\x00"),
                         ["OK    earlier t: bytes earlier 3, bytes now 5"])

    def test_a_byte_order_mark_is_part_of_the_bytes_compared(self):
        now = b"\xef\xbb\xbf" + b"k\tv\n" + k(1).encode() + b"\ta\n"
        found = self.earlier(now, b"k\tv\n")
        self.assertEqual(found, ["FAIL  earlier t: bytes earlier 4, bytes now %d" % len(now),
                                 "t.tsv:1: differs from the earlier copy"])


class OutputTest(RecordCase):
    FILES = {"t.tsv": tsv([["k", "g", "d"], [k(1), "A", "2026-01-05"], [k(1), "", "bad"]])}

    def test_checks_come_out_by_kind_then_in_declaration_order(self):
        declaration = "\n".join([
            "earlier:", "  t | t.old",
            "corrections:", "  t | c | d",
            "dates:", "  t | d", "  t | g",
            "values:", "  t | g | A",
            "required:", "  t | k", "  t | g",
            "references:", "  t | g | u | k | single", "  u | k | t | k | single",
            "tables:", "  u | u.tsv | tsv | k", "  t | t.tsv | tsv | k", ""])
        text = tsv([["k", "g", "c", "d"], [k(1), "A", "", "2026-01-01"],
                    [k(2), "B", k(1), "2026-01-02"]])
        _code, lines = self.lines(declaration, {"t.tsv": text, "u.tsv": tsv([["k"], [k(1)]]),
                                                "t.old": b"k"})
        labels = [line[6:].split(":")[0] for line in lines
                  if re.match(r"(OK  |FAIL|DEAD)  ", line)]
        self.assertEqual(labels, [
            "table u", "table t", "references t.g to u.k", "references u.k to t.k",
            "required t.k", "required t.g", "values t.g", "dates t.d", "dates t.g",
            "corrections t.c", "earlier t"])

    def test_the_status_and_exit_rules(self):
        files = {"t.tsv": tsv([["k", "g"], [k(1), ""]]), "u.tsv": tsv([["k", "g"], [k(1), "A"]])}
        ok = "tables:\n  u | u.tsv | tsv | k\nrequired:\n  u | g\n"
        fail = ok + "  t | g\n"
        dead = fail + "  u | zz\n"
        fail = fail.replace("tables:\n", "tables:\n  t | t.tsv | tsv | k\n")
        dead = dead.replace("tables:\n", "tables:\n  t | t.tsv | tsv | k\n")
        for label, declaration, plain, only, tail in (
                ("ok", ok, 0, 0, "checks: OK 2, FAIL 0, DEAD 0"),
                ("fail", fail, 1, 0, "checks: OK 3, FAIL 1, DEAD 0"),
                ("dead and fail", dead, 2, 2, "checks: OK 3, FAIL 1, DEAD 1")):
            with self.subTest(label):
                code, lines = self.lines(declaration, files)
                self.assertEqual((code, lines[-1]), (plain, tail))
                code, lines = self.lines(declaration, files, report_only=True)
                self.assertEqual((code, lines[-1]), (only, tail))

    def test_report_only_may_be_repeated(self):
        folder = self.folder()
        folder.put("t.tsv", tsv([["k"], [k(1)], [k(1)]]))
        folder.put("record.txt", "tables:\n  t | t.tsv | tsv | k\n")
        code, out, err = self.cli(["record", "--report-only", "--report-only",
                                   folder.path("record.txt")])
        self.assertEqual((code, err), (0, ""))

    def test_a_declared_path_is_printed_as_written_with_escapes(self):
        name = "sub" + os.sep + "t" + chr(7) + chr(9) + "x.tsv"
        folder = self.folder()
        os.mkdir(folder.path("sub"))
        folder.put(name, tsv([["k"], [k(1)], [k(1)]]))
        folder.put("record.txt", "tables:\n  t | %s | tsv | k\n" % name)
        _code, out, _err = self.cli(["record", folder.path("record.txt")])
        shown = "sub" + os.sep + "t\\x07\\tx.tsv"
        self.assertIn(shown + ":3: repeated key, first on line 2\n", out)
        self.assertEqual(len(out.split("\n")), 4)

    def test_a_column_name_is_printed_escaped(self):
        column = "c" + chr(7) + "d" + chr(0x200B)
        declaration = "tables:\n  t | t.tsv | tsv | k\nrequired:\n  t | %s\n" % column
        shown = "c\\x07d" + "\\" + "u200b"
        _code, lines = self.lines(declaration, {"t.tsv": tsv([["k"], [k(1)]])})
        self.assertEqual(lines[1], "DEAD  required t.%s: no column %s" % (shown, shown))


if __name__ == "__main__":
    unittest.main()
