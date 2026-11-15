"""Tests for ``track-record drafts``: bad input, DEAD checks, the command line, help, output
that cannot be written, the sentinel, and the readings that the spec leaves to the code. Every
draft file, version and note here is invented. The sentinel and traceback checks of
``RecordCase.tearDown`` apply to every run these tests make. Invisible and control characters
are written with chr(), never raw.
"""

import os
import unittest
import unittest.mock

from tests import test_drafts as d
from tests import test_record_check as base
from tests.test_drafts import counts, entry, fail, finding_lines, joined, lines_of, version
from tests.test_record_check import SENTINEL

from career_track_record import cli, drafts  # noqa: E402

NO_EARLIER_LINE = d.NO_EARLIER_LINE
ZERO = counts(0, 0, 0, 0, 0)
LETTER_COUNTS = counts(3, 3, 1, 1, 1)


def cannot(reason):
    return (2, "", "cannot run: %s\n" % reason)


def with_run(value):
    """A draft file of one version and one result entry whose run line is ``value``."""
    return version("v1") + entry("result", "v1", extra="run: %s\n" % value)


class DeadTest(d.DraftsCase):
    def dead(self, name, reason, c, content=None, args=()):
        folder = self.work()
        if content is not None:
            folder.put(name, content)
        want = "DEAD  %s: %s; %s\n" % (name, reason, c)
        got = self.check(name, *args)
        self.assertEqual(got, (2, want, ""))
        return folder, want

    def test_an_empty_file_is_dead(self):
        self.dead("empty.txt", "empty file", ZERO, b"")

    def test_a_file_that_is_only_a_byte_order_mark_is_empty(self):
        self.dead("bom.txt", "empty file", ZERO, b"\xef\xbb\xbf")

    def test_a_file_of_blank_lines_has_no_version(self):
        self.dead("blank.txt", "no version", ZERO, "\n \t\n\r\n\n")

    def test_a_file_of_entries_only_has_no_version(self):
        text = (entry("result", "v1", extra="run: runs/panel-01\n")
                + entry("send", "v1"))
        self.dead("entries.txt", "no version", counts(0, 0, 1, 1, 1), text)

    def test_a_file_whose_only_version_is_refused_has_no_version(self):
        self.dead("refused.txt", "no version", ZERO, version("v1", text="\n \n"))

    def test_an_earlier_copy_that_cannot_be_found_is_dead(self):
        self.dead("letter.txt", "earlier copy not found", LETTER_COUNTS,
                  args=("--earlier", "nothing.txt"))

    def test_an_earlier_copy_that_is_a_folder_cannot_be_read(self):
        self.dead("letter.txt", "earlier copy cannot be read", LETTER_COUNTS,
                  args=("--earlier", "runs"))

    def test_an_earlier_copy_that_is_a_fifo_is_never_opened(self):
        folder = self.work()
        os.mkfifo(folder.path("old.txt"))
        got = self.sub(["drafts", "check", "letter.txt", "--earlier", "old.txt"], timeout=20)
        self.assertEqual(got, (2, "DEAD  letter.txt: earlier copy cannot be read; %s\n"
                               % LETTER_COUNTS, ""))

    def test_an_empty_earlier_copy_is_dead(self):
        folder = self.work()
        folder.put("old.txt", b"")
        self.assertEqual(self.check("letter.txt", "--earlier", "old.txt"),
                         (2, "DEAD  letter.txt: earlier copy empty; %s\n" % LETTER_COUNTS, ""))

    def test_an_empty_string_earlier_path_is_still_given(self):
        self.work()
        self.assertEqual(self.check("letter.txt", "--earlier", ""),
                         (2, "DEAD  letter.txt: earlier copy not found; %s\n"
                          % LETTER_COUNTS, ""))

    def test_an_earlier_copy_that_is_the_draft_file_itself_is_dead(self):
        folder = self.work()
        os.symlink("letter.txt", folder.path("link.txt"))
        want = ("DEAD  letter.txt: earlier copy is the draft file itself; %s\n"
                % LETTER_COUNTS)
        self.assertEqual(self.check("letter.txt", "--earlier", "letter.txt"), (2, want, ""))
        self.assertEqual(self.check("letter.txt", "--earlier", "link.txt"), (2, want, ""))
        self.assertEqual(self.check("link.txt", "--earlier", "letter.txt"),
                         (2, want.replace("letter.txt:", "link.txt:"), ""))

    def test_r12_the_reasons_come_in_order(self):
        folder = self.work()
        folder.put("empty.txt", b"")
        folder.put("blank.txt", "\n\n")
        self.assertEqual(self.check("empty.txt", "--earlier", "nothing.txt")[1],
                         "DEAD  empty.txt: empty file; %s\n" % ZERO)
        self.assertEqual(self.check("blank.txt", "--earlier", "nothing.txt")[1],
                         "DEAD  blank.txt: no version; %s\n" % ZERO)

    def test_a_dead_extract_writes_its_line_to_standard_error_and_no_file(self):
        folder, want = self.dead("empty.txt", "empty file", ZERO, b"")
        self.assertEqual(self.extract("empty.txt", "v1", "--out", "o.txt"), (2, "", want))
        folder.put("blank.txt", "\n")
        got = self.extract("blank.txt", "v1", "--out", "o.txt")
        self.assertEqual(got, (2, "", "DEAD  blank.txt: no version; %s\n" % ZERO))
        got = self.extract("letter.txt", "v1", "--out", "o.txt", "--earlier", "nothing.txt")
        self.assertEqual(got, (2, "", "DEAD  letter.txt: earlier copy not found; %s\n"
                               % LETTER_COUNTS))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))

    def test_a_dead_file_gives_its_dead_line_even_for_an_id_it_does_not_have(self):
        self.work()
        got = self.extract("letter.txt", "v9", "--out", "o.txt", "--earlier", "nothing.txt")
        self.assertEqual(got[0], 2)
        self.assertTrue(got[2].startswith("DEAD  letter.txt: earlier copy not found;"))


class CannotRunTest(d.DraftsCase):
    def refused(self, args, reason):
        folder = self.work()
        before = sorted(os.listdir(folder.dir))
        self.assertEqual(self.cli(["drafts"] + args), cannot(reason))
        self.assertEqual(sorted(os.listdir(folder.dir)), before)
        return folder

    def test_10_an_unknown_option(self):
        """each case of section 8 exits 2 with its `cannot run:` line: an unknown option"""
        self.refused(["check", "letter.txt", "--bogus"], "unknown option --bogus")
        self.refused(["extract", "letter.txt", "v1", "--out", "o.txt", "--bogus=1"],
                     "unknown option --bogus")

    def test_10_earlier_given_twice(self):
        """`--earlier` given twice"""
        self.refused(["check", "letter.txt", "--earlier", "a", "--earlier", "b"],
                     "--earlier given more than once")
        self.refused(["extract", "letter.txt", "v1", "--out", "o.txt", "--earlier=a",
                      "--earlier", "b"], "--earlier given more than once")

    def test_10_extract_with_no_out(self):
        """`extract` with no `--out`"""
        self.refused(["extract", "letter.txt", "v1"], "extract needs --out OUT")

    def test_10_two_files(self):
        """two FILEs"""
        self.refused(["check", "letter.txt", "letter-before.txt"],
                     "check takes one FILE, not several")
        self.refused(["extract", "letter.txt", "v1", "letter-before.txt", "--out", "o.txt"],
                     "extract takes one FILE, not several")

    def test_10_an_id_that_no_version_has(self):
        """`extract letter.txt v9 --out v9.txt`, which gives `cannot run: no version v9`"""
        self.refused(["extract", "letter.txt", "v9", "--out", "v9.txt"], "no version v9")

    def test_10_an_existing_out(self):
        """an existing `OUT`"""
        folder = self.work()
        folder.put("o.txt", b"keep")
        self.assertEqual(self.extract("letter.txt", "v3", "--out", "o.txt"),
                         cannot("--out names a path that already exists"))
        with open(folder.path("o.txt"), "rb") as handle:
            self.assertEqual(handle.read(), b"keep")

    def test_10_no_file(self):
        """no FILE"""
        self.refused(["check"], "check needs a FILE")
        self.refused(["extract"], "extract needs a FILE")
        self.refused(["check", "--earlier", "letter-before.txt"], "check needs a FILE")
        self.refused(["extract", "--out", "o.txt"], "extract needs a FILE")

    def test_10_no_id(self):
        """no id"""
        self.refused(["extract", "letter.txt", "--out", "o.txt"], "extract needs a version id")

    def test_10_a_missing_or_unknown_subcommand(self):
        """a missing subcommand, an unknown subcommand"""
        self.refused([], "drafts needs check or extract")
        self.refused(["verify", "letter.txt"], "unknown subcommand verify")
        self.refused(["--bogus"], "unknown subcommand --bogus")
        self.refused(["--"], "unknown subcommand --")
        self.refused(["-"], "unknown subcommand -")

    def test_10_a_draft_file_that_does_not_exist(self):
        """a draft file that does not exist"""
        folder = self.work()
        os.mkdir(folder.path("sub"))
        self.assertEqual(self.check("nothing.txt"),
                         cannot("cannot read the draft file: nothing.txt"))
        self.assertEqual(self.check("sub/nothing.txt"),
                         cannot("cannot read the draft file: nothing.txt"))
        self.assertEqual(self.extract("nothing.txt", "v1", "--out", "o.txt"),
                         cannot("cannot read the draft file: nothing.txt"))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))

    def test_a_name_with_a_line_break_or_a_control_character_is_escaped(self):
        folder = self.work()
        bad = "x" + chr(10) + "y" + chr(7) + ".txt"
        self.assertEqual(self.check(bad), cannot("cannot read the draft file: x\\ny\\x07.txt"))
        folder.put(bad, b"")
        self.assertEqual(self.check(bad)[1][:len("DEAD  x\\ny\\x07.txt: empty file")],
                         "DEAD  x\\ny\\x07.txt: empty file")
        self.assertEqual(self.cli(["drafts", "check", "letter.txt", "--b" + chr(10) + "c"]),
                         cannot("unknown option --b\\nc"))
        self.assertEqual(self.extract("letter.txt", "v" + chr(10) + "9", "--out", "o.txt"),
                         cannot("no version v\\n9"))
        self.assertEqual(self.cli(["drafts", "q" + chr(10) + "r"]),
                         cannot("unknown subcommand q\\nr"))

    def test_r14_a_draft_file_that_is_not_utf_8_or_not_a_regular_file(self):
        folder = self.work()
        folder.put("bad.txt", b"## v1\n\xff\xfe\n")
        os.mkdir(folder.path("folder.txt"))
        os.mkfifo(folder.path("fifo.txt"))
        for name in ("bad.txt", "folder.txt", "fifo.txt"):
            with self.subTest(name):
                got = self.sub(["drafts", "check", name], timeout=20)
                self.assertEqual(got, cannot("cannot read the draft file: " + name))
                got = self.sub(["drafts", "extract", name, "v1", "--out", "o.txt"], timeout=20)
                self.assertEqual(got, cannot("cannot read the draft file: " + name))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))

    def test_r14_a_byte_order_mark_is_dropped(self):
        folder = self.work()
        folder.put("bom.txt", b"\xef\xbb\xbf" + text_bytes())
        got = self.check("bom.txt")
        self.assertEqual(got[0], 0)
        self.assertTrue(got[1].startswith("OK    bom.txt: " + LETTER_COUNTS))
        self.assertEqual(self.check("bom.txt", "--earlier", "letter.txt")[1][:4], "FAIL")

    def test_r1_the_bare_forms_are_cannot_run_cases(self):
        self.refused([], "drafts needs check or extract")
        self.refused(["check"], "check needs a FILE")
        self.refused(["extract"], "extract needs a FILE")

    def test_r15_one_line_and_the_first_problem(self):
        folder = self.work()
        folder.put("o.txt", b"keep")
        cases = [
            (["extract", "--bogus", "--earlier", "a", "--earlier", "b"], "unknown option --bogus"),
            (["extract", "a", "b", "c", "--out", "o.txt", "--bogus"], "unknown option --bogus"),
            (["extract", "a", "b", "c", "--out", "o.txt"],
             "extract takes one FILE, not several"),
            (["extract", "--out", "o.txt"], "extract needs a FILE"),
            (["extract", "letter.txt"], "extract needs a version id"),
            (["check", "--out", "o.txt", "letter.txt"], "unknown option --out"),
            (["extract", "letter.txt", "v1", "--out", "o.txt"],
             "--out names a path that already exists"),
            (["extract", "nothing.txt", "v1", "--out", "o.txt"],
             "--out names a path that already exists"),
            (["frob", "--earlier", "a", "--earlier", "b"], "unknown subcommand frob"),
        ]
        for args, reason in cases:
            with self.subTest(args):
                self.assertEqual(self.cli(["drafts"] + args), cannot(reason))
        with unittest.mock.patch.object(drafts, "rule_2", lambda *a, **k: []):
            self.assertEqual(self.extract("nothing.txt", "v1", "--out", "new.txt"),
                             cannot("self-test failed: rule 2"))
        self.assertEqual(self.extract("nothing.txt", "v1", "--out", "new.txt"),
                         cannot("cannot read the draft file: nothing.txt"))

    def test_r15_an_id_that_no_version_has_is_checked_after_dead_and_before_a_fault(self):
        folder = self.work()
        lines = lines_of(d.text_of("letter.txt"))
        lines[10] = "parent: v9"
        folder.put("faulty.txt", joined(lines))
        self.assertEqual(self.extract("faulty.txt", "v9", "--out", "o.txt"),
                         cannot("no version v9"))
        got = self.extract("faulty.txt", "v1", "--out", "o.txt")
        self.assertEqual(got[0], 1)
        self.assertFalse(os.path.lexists(folder.path("o.txt")))
        folder.put("rejected.txt", version("v1") + "## v2\nWords.\n")
        self.assertEqual(self.extract("rejected.txt", "v2", "--out", "o.txt"),
                         cannot("no version v2"))

    def test_r16_an_option_with_equals_is_the_same_as_two_words(self):
        folder = self.work()
        a = self.check("letter.txt", "--earlier", "letter-before.txt")
        b = self.check("letter.txt", "--earlier=letter-before.txt")
        self.assertEqual(a, b)
        got = self.extract("letter.txt", "v3", "--out=o.txt", "--earlier=letter-before.txt")
        self.assertEqual(got, (0, "", ""))
        self.assertTrue(os.path.isfile(folder.path("o.txt")))

    def test_r16_a_missing_value(self):
        self.refused(["check", "letter.txt", "--earlier"], "--earlier needs a value")
        self.refused(["check", "letter.txt", "--earlier", "--earlier", "a"],
                     "--earlier needs a value")
        self.refused(["extract", "letter.txt", "v1", "--earlier", "--out", "o.txt"],
                     "--earlier needs a value")
        self.refused(["extract", "letter.txt", "v1", "--out", "--earlier", "a"],
                     "--out needs a value")
        self.refused(["extract", "letter.txt", "v1", "--out"], "--out needs a value")
        self.refused(["check", "letter.txt", "--earlier="], "--earlier needs a value")
        self.refused(["extract", "letter.txt", "v1", "--out="], "--out needs a value")

    def test_r16_out_given_twice(self):
        self.refused(["extract", "letter.txt", "v1", "--out", "a", "--out", "b"],
                     "--out given more than once")
        self.refused(["extract", "letter.txt", "v1", "--out=a", "--out=b"],
                     "--out given more than once")

    def test_r16_an_abbreviation_is_an_unknown_option(self):
        self.refused(["check", "letter.txt", "--earl", "letter-before.txt"],
                     "unknown option --earl")
        self.refused(["extract", "letter.txt", "v1", "--o", "x"], "unknown option --o")
        self.refused(["check", "letter.txt", "--out", "x"], "unknown option --out")

    def test_r16_after_two_dashes_every_argument_is_a_word(self):
        folder = self.work()
        folder.put("--help", d.text_of("letter.txt"))
        folder.put("--earlier", d.text_of("letter.txt"))
        got = self.check("--", "--help")
        self.assertEqual(got[0], 0)
        self.assertTrue(got[1].startswith("OK    --help: "))
        got = self.check("--", "--earlier")
        self.assertTrue(got[1].startswith("OK    --earlier: "))
        self.refused(["check", "--", "letter.txt", "--earlier"],
                     "check takes one FILE, not several")

    def test_r16_a_single_dash_is_a_file_name(self):
        self.refused(["check", "-"], "cannot read the draft file: -")
        self.work()
        got = self.check("letter.txt", "--earlier", "-")
        self.assertEqual(got[1][:35], "DEAD  letter.txt: earlier copy not ")


def text_bytes():
    return d.text_of("letter.txt").encode("utf-8")


class HelpTest(d.DraftsCase):
    HELPS = [["drafts", "-h"], ["drafts", "--help"], ["drafts", "check", "--help"],
             ["drafts", "check", "-h"], ["drafts", "extract", "--help"],
             ["drafts", "extract", "-h"], ["drafts", "check", "--earlier", "--help"],
             ["drafts", "extract", "--out", "-h"], ["drafts", "check", "letter.txt", "--help"],
             ["drafts", "extract", "letter.txt", "v1", "--out", "o.txt", "--help"],
             ["drafts", "--bogus", "-h"], ["drafts", "frob", "--help"],
             ["drafts", "check", "--bogus", "--help"], ["drafts", "check", "-h", "--bogus"]]

    def test_help_at_every_level_and_beside_other_arguments(self):
        folder = self.work()
        for args in self.HELPS:
            with self.subTest(args):
                self.assertEqual(self.cli(args), (0, cli._DRAFTS_HELP, ""))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))

    def test_help_in_a_process_of_its_own(self):
        self.assertEqual(self.sub(["drafts", "--help"]), (0, cli._DRAFTS_HELP, ""))

    def test_the_help_constant_is_the_specs_summary(self):
        spec = base.read(d.SPEC)
        self.assertEqual(base.fenced_after(spec, "The summary is the text below"),
                         cli._DRAFTS_HELP)
        self.assertEqual(len(cli._DRAFTS_HELP.encode("utf-8")), 480)
        self.assertTrue(cli._DRAFTS_HELP.endswith("\n"))
        self.assertFalse(cli._DRAFTS_HELP.endswith("\n\n"))

    def test_the_top_level_help_lists_the_command(self):
        code, out, err = self.sub(["--help"])
        self.assertIn("drafts", out)
        self.assertIn("check a file of a document's versions, or extract one", out)


class OutputFailureTest(d.DraftsCase):
    def test_closed_standard_output_is_one_line_on_standard_error(self):
        self.work()
        for args in (["drafts", "check", "letter.txt"], ["drafts", "--help"],
                     ["drafts", "check", "--help"]):
            with self.subTest(args):
                self.assertEqual(self.sub(args, shell_tail=">&-"), (2, "", base.NO_OUTPUT))

    def test_a_pipe_whose_reader_is_gone_is_the_same_failure(self):
        self.work()
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            p = base.subprocess.run(base.CMD + ["drafts", "check", "letter.txt"],
                                    env=base.env(), stdin=base.subprocess.DEVNULL,
                                    stdout=write_end, stderr=base.subprocess.PIPE, timeout=30)
        finally:
            os.close(write_end)
        self.assertEqual((p.returncode, p.stderr.decode("utf-8")), (2, base.NO_OUTPUT))

    def test_closed_standard_error_changes_nothing_for_check(self):
        self.work()
        got = self.sub(["drafts", "check", "letter.txt", "--earlier", "letter-before.txt"],
                       shell_tail="2>&-")
        self.assertEqual(got, (0, d.OK_LINE + "\n", ""))
        got = self.sub(["drafts", "check", "letter-edited.txt", "--earlier",
                        "letter-before.txt"], shell_tail="2>&-")
        self.assertEqual(got, (1, d.FAIL_EDITED, ""))

    def test_r18_closed_standard_error_stops_an_extract_that_must_write_a_line(self):
        folder = self.work()
        got = self.sub(["drafts", "extract", "letter.txt", "v3", "--out", "o.txt"],
                       shell_tail="2>&-")
        self.assertEqual(got, (2, "", ""))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))
        got = self.sub(["drafts", "extract", "letter-edited.txt", "v2", "--out", "o.txt",
                        "--earlier", "letter-before.txt"], shell_tail="2>&-")
        self.assertEqual(got, (2, "", ""))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))

    def test_r18_closed_standard_error_does_not_stop_an_extract_with_nothing_to_say(self):
        folder = self.work()
        got = self.sub(["drafts", "extract", "letter.txt", "v3", "--out", "o.txt", "--earlier",
                        "letter-before.txt"], shell_tail="2>&-")
        self.assertEqual(got, (0, "", ""))
        self.assertEqual(os.path.getsize(folder.path("o.txt")), 66)

    def test_r18_standard_error_that_fails_in_process_writes_no_file(self):
        folder = self.work()

        def broken(_text):
            raise OSError("no")
        with unittest.mock.patch.object(cli, "_write", side_effect=OSError("no")):
            got = self.extract("letter.txt", "v3", "--out", "o.txt")
        self.assertEqual(got, (2, "", ""))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))
        got = drafts.extract("letter.txt", "v3", "o.txt", emit=broken)
        self.assertEqual((got.exit_code, got.ran, got.error), (2, False,
                                                              "cannot run: cannot write output"))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))


class WritingOutTest(d.DraftsCase):
    def test_r17_an_out_in_a_folder_that_does_not_exist(self):
        folder = self.work()
        self.assertEqual(self.extract("letter.txt", "v3", "--out", "missing/o.txt",
                                      "--earlier", "letter-before.txt"),
                         cannot("cannot write output"))
        self.assertFalse(os.path.lexists(folder.path("missing")))

    def test_r17_a_dangling_link_as_out_is_an_existing_path(self):
        folder = self.work()
        os.symlink("target.txt", folder.path("o.txt"))
        self.assertEqual(self.extract("letter.txt", "v3", "--out", "o.txt"),
                         cannot("--out names a path that already exists"))
        self.assertFalse(os.path.exists(folder.path("target.txt")))
        self.assertTrue(os.path.islink(folder.path("o.txt")))

    def test_r17_a_link_to_a_file_as_out_is_never_written_through(self):
        folder = self.work()
        folder.put("target.txt", b"keep")
        os.symlink("target.txt", folder.path("o.txt"))
        self.assertEqual(self.extract("letter.txt", "v3", "--out", "o.txt")[0], 2)
        with open(folder.path("target.txt"), "rb") as handle:
            self.assertEqual(handle.read(), b"keep")

    def test_r17_a_path_made_between_the_lookup_and_the_write_is_never_opened(self):
        folder = self.work()
        folder.put("o.txt", b"keep")
        with unittest.mock.patch.object(drafts, "_exists", lambda path: False):
            got = self.extract("letter.txt", "v3", "--out", "o.txt", "--earlier",
                               "letter-before.txt")
        self.assertEqual(got, cannot("cannot write output"))
        with open(folder.path("o.txt"), "rb") as handle:
            self.assertEqual(handle.read(), b"keep")

    def test_r17_a_write_that_fails_part_way_removes_the_file_it_made(self):
        folder = self.work()
        with unittest.mock.patch.object(drafts.os, "write", side_effect=OSError("full")):
            got = self.extract("letter.txt", "v3", "--out", "o.txt", "--earlier",
                               "letter-before.txt")
        self.assertEqual(got, cannot("cannot write output"))
        self.assertFalse(os.path.lexists(folder.path("o.txt")))

    def test_r27_a_line_already_written_to_standard_error_stays_when_out_cannot_be_made(self):
        self.work()
        got = self.extract("letter.txt", "v3", "--out", "missing/o.txt")
        self.assertEqual(got, (2, "", NO_EARLIER_LINE + "cannot run: cannot write output\n"))

    def test_r17_an_out_with_a_nul_character_cannot_be_written(self):
        self.work()
        self.assertEqual(self.extract("letter.txt", "v3", "--out", "o" + chr(0) + ".txt",
                                      "--earlier", "letter-before.txt"),
                         cannot("cannot write output"))

    def test_r17_extract_never_writes_to_the_draft_file(self):
        folder = self.work()
        before = d.text_of("letter.txt")
        self.extract("letter.txt", "v3", "--out", "o.txt")
        self.extract("letter.txt", "v1", "--out", "p.txt", "--earlier", "letter-before.txt")
        self.assertEqual(base.read(folder.path("letter.txt")), before)
        self.assertEqual(sorted(os.listdir(folder.dir)),
                         sorted(list(d.NAMES) + ["o.txt", "p.txt", "runs"]))

    def test_r18_a_stop_has_no_extra_line_and_no_earlier_line(self):
        folder = self.work()
        lines = lines_of(d.text_of("letter.txt"))
        lines[10] = "parent: v9"
        folder.put("faulty.txt", joined(lines))
        code, out, err = self.check("faulty.txt")
        self.assertEqual(self.extract("faulty.txt", "v1", "--out", "o.txt"), (1, "", out))
        self.assertTrue(out.endswith("no earlier copy given\nfaulty.txt:11: parent not found\n"))

    def test_r19_a_stopped_extract_lists_the_run_folder_finding_too(self):
        folder = self.work()
        os.rmdir(folder.path("runs/panel-01"))
        lines = lines_of(d.text_of("letter.txt"))
        lines[10] = "parent: v9"
        folder.put("faulty.txt", joined(lines))
        want = (fail("faulty.txt", counts(3, 2, 1, 0, 1), 2)
                + "faulty.txt:11: parent not found\nfaulty.txt:22: run folder not found\n")
        self.assertEqual(self.check("faulty.txt"), (1, want, ""))
        self.assertEqual(self.extract("faulty.txt", "v1", "--out", "o.txt"), (1, "", want))

    def test_r20_the_draft_file_the_copy_and_out_are_read_as_given(self):
        folder = self.work()
        os.mkdir(folder.path("sub"))
        for name in ("letter.txt", "letter-before.txt"):
            os.rename(folder.path(name), folder.path("sub/" + name))
        os.rename(folder.path("runs"), folder.path("sub/runs"))
        got = self.check("sub/letter.txt", "--earlier", "sub/letter-before.txt")
        self.assertEqual(got[0], 0)
        self.assertTrue(got[1].startswith("OK    sub/letter.txt: " + LETTER_COUNTS))
        self.assertEqual(self.extract("sub/letter.txt", "v3", "--out", "o.txt")[0], 0)
        self.assertTrue(os.path.isfile(folder.path("o.txt")))
        self.assertFalse(os.path.lexists(folder.path("sub/o.txt")))
        got = self.check("letter.txt")
        self.assertEqual(got, cannot("cannot read the draft file: letter.txt"))

    def test_r20_a_run_folder_is_read_from_the_draft_files_folder(self):
        folder = self.work()
        os.mkdir(folder.path("sub"))
        folder.put("sub/draft.txt", d.text_of("letter.txt"))
        self.assertTrue(os.path.isdir(folder.path("runs/panel-01")))
        got = self.check("sub/draft.txt")
        self.assertEqual(got[0], 1)
        self.assertIn("run folders found 0", got[1])
        self.assertIn("sub/draft.txt:22: run folder not found", got[1])
        os.makedirs(folder.path("sub/runs/panel-01"))
        self.assertEqual(self.check("sub/draft.txt")[0], 0)


class ReadingsTest(d.DraftsCase):
    def check_text(self, text, name="draft.txt"):
        folder = self.work()
        folder.put(name, text)
        return folder, self.check(name)

    def expect(self, text, c, found, name="draft.txt", send="none"):
        folder, got = self.check_text(text, name)
        if found:
            want = fail(name, c, len(found)) + finding_lines(name, found)
            self.assertEqual(got, (1, want, ""))
        else:
            self.assertEqual(got, (0, "OK    %s: %s; send copy %s; no earlier copy given\n"
                                   % (name, c, send), ""))
        return folder

    def test_r3_a_key_line_is_exactly_the_key_a_colon_and_a_space(self):
        base_text = version("v1") + entry("result", "v1", extra="run: runs/panel-01\n")
        self.expect(base_text + "note:\n", counts(1, 1, 0, 0, 0), [(11, "unknown key")])
        self.expect(base_text + "note: \n", counts(1, 1, 1, 1, 0), [])
        self.expect(base_text + "note: x\n", counts(1, 1, 1, 1, 0), [])
        second = version("v2", parent="v1")
        for old, new, missing in (("change: first", "change:first", "change"),
                                  ("change: first", "change:", "change"),
                                  ("\ntext:\n", "\ntext: x\n", "text"),
                                  ("\ntext:\n", "\ntext:  \n", "text")):
            with self.subTest(new):
                self.expect(version("v1") + second.replace(old, new), counts(1, 1, 0, 0, 0),
                            [(7, "no %s line" % missing)])

    def test_r3_a_blank_line_among_a_versions_key_lines_is_an_unknown_key(self):
        text = version("v1") + version("v2", parent="v1").replace("date:", "\ndate:")
        self.expect(text, counts(1, 1, 0, 0, 0), [(9, "unknown key")])

    def test_r3_spaces_and_tabs_after_an_entry_are_blank(self):
        self.expect(version("v1") + entry("send", "v1") + " \t \n",
                    counts(1, 1, 0, 0, 1), [], send="v1")

    def test_r4_a_number_with_a_leading_zero_is_not_an_id(self):
        text = version("v1", text="one\n## v01\ntwo\n")
        self.expect(text, counts(1, 1, 0, 0, 0), [])
        draft = drafts.read_draft(drafts.split_lines(text))
        self.assertEqual(drafts.version_bytes(draft.sections[0]), b"one\n## v01\ntwo\n")

    def test_r4_a_header_with_a_leading_zero_after_an_entry_or_before_a_section(self):
        text = version("v1") + entry("send", "v1") + "\n## v01\n"
        self.expect(text, counts(1, 1, 0, 0, 0), [(11, "line after an entry")])
        self.expect("## v01\n" + version("v1"), counts(1, 1, 0, 0, 0),
                    [(1, "line before the first section")])

    def test_r4_ids_increase_by_number_not_by_text(self):
        ok = version("v9") + version("v10", parent="v9") + version("v100", parent="v10")
        self.expect(ok, counts(3, 3, 0, 0, 0), [])
        bad = version("v10") + version("v9", parent="v10")
        self.expect(bad, counts(2, 2, 0, 0, 0), [(7, "id out of order, line 1")])
        zero = version("v0") + version("v1", parent="v0")
        self.expect(zero, counts(2, 2, 0, 0, 0), [])

    def test_r26_ids_are_compared_without_turning_them_into_integers(self):
        small = "v" + "9" * 5000
        large = "v1" + "0" * 5000
        self.expect(version(small) + version(large, parent=small), counts(2, 2, 0, 0, 0), [])
        self.expect(version(large) + version(small, parent=large), counts(2, 2, 0, 0, 0),
                    [(7, "id out of order, line 1")])

    def test_r4_a_parent_matches_an_id_only_when_the_strings_are_equal(self):
        text = version("v1") + version("v2", parent="v01")
        self.expect(text, counts(2, 1, 0, 0, 0), [(8, "parent not found")])
        text = version("v1") + entry("result", "v01", extra="run: runs/panel-01\n")
        self.expect(text, counts(1, 1, 1, 1, 0), [(8, "version not found")])

    def test_r5_a_finding_for_each_line_before_the_first_section(self):
        text = "one\n\n  \ntwo\n" + version("v1")
        self.expect(text, counts(1, 1, 0, 0, 0),
                    [(1, "line before the first section"),
                     (4, "line before the first section")])

    def test_r6_a_repeated_id_gets_only_the_repeated_finding(self):
        text = version("v2") + version("v1") + version("v1")
        self.expect(text, counts(3, 3, 0, 0, 0),
                    [(7, "id out of order, line 1"), (13, "repeated id, first on line 7")])

    def test_r7_the_first_version_gets_one_finding_and_nothing_else(self):
        self.expect(version("v1", parent="v1"), counts(1, 0, 0, 0, 0),
                    [(2, "first version has a parent")])
        self.expect(version("v1", parent="v7") + version("v2"), counts(2, 1, 0, 0, 0),
                    [(2, "first version has a parent")])

    def test_r7_a_parent_that_comes_later_names_the_first_such_version(self):
        text = version("v1") + version("v2", parent="v3") + version("v3") + version("v3")
        self.expect(text, counts(4, 3, 0, 0, 0),
                    [(8, "parent comes later, line 13"), (19, "repeated id, first on line 13")])

    def test_r7_a_parent_that_is_itself_comes_before_an_earlier_version_with_the_id(self):
        text = version("v1") + version("v2", parent="v1") + version("v2", parent="v2")
        self.expect(text, counts(3, 2, 0, 0, 0),
                    [(13, "repeated id, first on line 7"), (14, "parent is itself")])

    def test_r7_none_holds_and_counts_as_resolved(self):
        text = version("v1") + version("v2") + version("v3", parent="none")
        self.expect(text, counts(3, 3, 0, 0, 0), [])

    def test_r8_a_change_note_of_spaces_and_tabs_is_empty(self):
        for note in ("", " ", "  \t "):
            with self.subTest(note):
                self.expect(version("v1", change=note), counts(1, 1, 0, 0, 0),
                            [(4, "empty change note")])

    def test_r8_what_a_run_folder_is_found_as(self):
        folder = self.work()
        with open(folder.path("runs/a-file"), "wb") as handle:
            handle.write(b"x")
        os.symlink("panel-01", folder.path("runs/link"))
        os.symlink("a-file", folder.path("runs/filelink"))
        cases = [("runs/panel-01", True), ("runs/../runs/panel-01", True), ("runs/link", True),
                 ("runs/a-file", False), ("runs/filelink", False), ("runs/none", False),
                 ("", False), (" \t ", False), ("/", False), (folder.path("runs/panel-01"), False),
                 ("runs/panel-01 ", False)]
        for value, found in cases:
            with self.subTest(value):
                folder.put("draft.txt", with_run(value))
                code, out, err = self.check("draft.txt")
                self.assertEqual(err, "")
                if found:
                    self.assertEqual(code, 0)
                    self.assertIn("run folders found 1", out)
                else:
                    self.assertEqual(code, 1)
                    self.assertIn("run folders found 0", out)
                    self.assertTrue(out.endswith("draft.txt:10: run folder not found\n"))

    def test_r8_a_blank_run_is_missing_even_when_the_joined_path_is_a_folder(self):
        text = (version("v1")
                + entry("result", "v1", extra="run:  \t \n")
                + entry("result", "v1", extra="run: runs/ready\n"))
        accepted = drafts.read_draft(drafts.split_lines(text)).accepted()
        self.assertEqual(drafts.rule_9(accepted, "folder", lambda _path: True),
                         [(10, "run folder not found")])

    def test_r9_a_date_that_is_not_a_real_day_is_not_compared(self):
        text = version("v1", date="2026-01-05") + version("v2", date="2026-13-01")
        self.expect(text, counts(2, 2, 0, 0, 0), [(9, "not a date")])
        text = version("v1", date="2026-01-05") + version("v2", date="2026-1-1")
        self.expect(text, counts(2, 2, 0, 0, 0), [(9, "not a date")])

    def test_r9_a_section_is_compared_with_the_nearest_section_rule_1_accepts(self):
        text = (version("v1", date="2026-02-01") + version("v2", date="2026-01-01", text="\n")
                + version("v3", date="2026-01-15"))
        self.expect(text, counts(2, 2, 0, 0, 0),
                    [(7, "empty text"), (15, "dated before the section on line 1")])

    def test_r9_the_same_day_is_not_a_fault(self):
        self.expect(version("v1") + version("v2") + entry("send", "v2"),
                    counts(2, 2, 0, 0, 1), [], send="v2")

    def test_r10_the_finding_with_no_line_comes_after_every_finding_with_a_line(self):
        folder = self.work()
        lines = lines_of(d.text_of("letter-before.txt"))
        lines[10] = "parent: v9"
        text = joined(lines)
        folder.put("short.txt", text)
        folder.put("long.txt", text + "tail\n")
        code, out, err = self.check("short.txt", "--earlier", "long.txt")
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail("short.txt", counts(2, 1, 0, 0, 0), 2,
                                   "earlier copy %d bytes, file %d bytes"
                                   % (len(text) + 5, len(text)))
                         + "short.txt:11: parent not found\nshort.txt: shorter than the earlier "
                           "copy\n")

    def test_r11_the_counts_count_only_the_sections_rule_1_accepts(self):
        text = (version("v1") + entry("result", "v1", extra="run: runs/panel-01\n")
                + "## result\nversion: v1\ndate: 2026-01-01\n\n"
                + "## send\nversion: v1\ndate: 2026-01-01\ncolour: red\n"
                + "## v2\nparent: none\n")
        folder, got = self.check_text(text)
        self.assertEqual(got[0], 1)
        self.assertTrue(got[1].startswith(
            "FAIL  draft.txt: %s; faults 3;" % counts(1, 1, 1, 1, 0)))

    def test_r21_an_upper_case_digest_does_not_match(self):
        digest = d.digests(version("v1"))["v1"]
        self.expect(version("v1", extra="sha256: " + digest + "\n"), counts(1, 1, 0, 0, 0), [])
        self.expect(version("v1", extra="sha256: " + digest.upper() + "\n"),
                    counts(1, 1, 0, 0, 0), [(5, "sha256 does not match the text")])
        self.expect(version("v1", extra="sha256: " + digest[:-1] + "\n"),
                    counts(1, 1, 0, 0, 0), [(5, "sha256 does not match the text")])

    def test_r22_a_text_ends_at_the_header_line_of_a_section_rule_1_refuses(self):
        text = version("v1", text="alpha\n## send\nbeta\n")
        draft = drafts.read_draft(drafts.split_lines(text))
        self.assertEqual(drafts.version_bytes(draft.sections[0]), b"alpha\n")
        self.expect(text, counts(1, 1, 0, 0, 0), [(7, "no version line after the header")])

    def test_r23_only_lf_crlf_and_a_lone_cr_end_a_line(self):
        odd = "a" + chr(0x0C) + "b" + chr(0x85) + "c" + chr(0x2028) + "d"
        folder = self.work()
        folder.put("odd.txt", version("v1", text=odd + "\n"))
        self.assertEqual(self.extract("odd.txt", "v1", "--out", "o.txt")[0], 0)
        with open(folder.path("o.txt"), "rb") as handle:
            self.assertEqual(handle.read(), (odd + "\n").encode("utf-8"))
        for char in (chr(0x0C), chr(0x85), chr(0x2028), chr(0xA0)):
            with self.subTest(hex(ord(char))):
                self.expect(version("v1", text=char + "\n"), counts(1, 1, 0, 0, 0), [])
        self.expect(version("v1") + version("v2", parent="v1", text=" \t\n"),
                    counts(1, 1, 0, 0, 0), [(7, "empty text")])

    def test_r23_a_final_line_break_starts_no_line(self):
        text = version("v1")
        self.expect(text, counts(1, 1, 0, 0, 0), [])
        self.expect(text[:-1], counts(1, 1, 0, 0, 0), [])
        self.expect(text.replace("\n", "\r"), counts(1, 1, 0, 0, 0), [])
        self.expect(text.replace("\n", "\r\n"), counts(1, 1, 0, 0, 0), [])

    def test_the_byte_order_mark_is_dropped_and_counted_in_the_file_size(self):
        folder = self.work()
        data = b"\xef\xbb\xbf" + version("v1").encode("utf-8")
        folder.put("bom.txt", data)
        folder.put("old.txt", data)
        folder.put("new.txt", data + b"\n## send\nversion: v1\ndate: 2026-01-01\n")
        code, out, err = self.check("new.txt", "--earlier", "old.txt")
        self.assertEqual(code, 0)
        self.assertTrue(out.endswith("send copy v1; earlier copy %d bytes, file %d bytes\n"
                                     % (len(data), len(data) + 38)))

    def test_rule_8_names_the_line_of_the_first_differing_byte_in_crlf_files(self):
        folder = self.work()
        text = version("v1").replace("\n", "\r\n")
        folder.put("old.txt", text.replace("Words.", "Wards.").encode())
        folder.put("new.txt", text.encode())
        code, out, err = self.check("new.txt", "--earlier", "old.txt")
        self.assertEqual(code, 1)
        self.assertTrue(out.endswith("new.txt:6: differs from the earlier copy\n"))
        folder.put("old.txt", b"a\rX")
        folder.put("new.txt", b"a\r\nb")
        data = b"a\r\nb"
        self.assertEqual(drafts.rule_8(data, b"a\rX"), [(1, "differs from the earlier copy")])
        self.assertEqual(drafts.rule_8(b"a\nb", b"a\nc"), [(2, "differs from the earlier copy")])

    def test_rule_8_accepts_a_byte_equal_earlier_copy(self):
        folder = self.work()
        data = version("v1")
        folder.put("same.txt", data)
        folder.put("old.txt", data)
        code, out, err = self.check("same.txt", "--earlier", "old.txt")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.endswith("earlier copy %d bytes, file %d bytes\n"
                                     % (len(data), len(data))))

    def test_rule_8_handles_a_difference_at_byte_zero(self):
        self.assertEqual(drafts.rule_8(b"a", b"b"),
                         [(1, "differs from the earlier copy")])

    def test_rule_8_counts_a_differing_line_feed_on_the_line_before_it(self):
        self.assertEqual(drafts.rule_8(b"a\nb", b"aXb"),
                         [(1, "differs from the earlier copy")])


class SentinelTest(d.DraftsCase):
    def draft(self):
        words = lambda n: "%s-%02d" % (SENTINEL, n)  # noqa: E731
        return (version("v1", change="change " + words(1), text="text %s\n" % words(2))
                + entry("result", "v1", extra="run: runs/panel-01\nnote: note %s\n" % words(3))
                + version("v2", parent="v1", change="change " + words(4),
                          text="text %s\n\nmore %s\n" % (words(5), words(6)))
                + entry("send", "v2"))

    def test_the_sentinel_is_in_no_output_of_any_kind_of_run(self):
        folder = self.work()
        text = self.draft()
        self.assertEqual(text.count(SENTINEL), 6)
        faults = {
            "rule1": text + "\n## v3\n" + SENTINEL + "\n",
            "rule2": text + version("v2", parent="v1", change=SENTINEL, text=SENTINEL + "\n"),
            "rule3": text.replace("parent: v1\n", "parent: v8\n"),
            "rule4": text.replace("change: change", "change: "),
            "rule5": text.replace("date: 2026-01-01\nchange: change " + SENTINEL + "-04",
                                  "date: 2025-01-01\nchange: change " + SENTINEL + "-04"),
            "rule6": text + entry("send", "v2"),
            "rule7": text.replace("change: change " + SENTINEL + "-04\n",
                                  "change: change " + SENTINEL + "-04\nsha256: " + "0" * 64
                                  + "\n"),
            "rule9": text.replace("runs/panel-01", "runs/" + "gone"),
            "parent-value": text.replace("parent: v1\n", "parent: " + SENTINEL + "\n"),
            "version-value": text.replace("version: v1\n", "version: " + SENTINEL + "\n"),
            "date-value": text.replace("date: 2026-01-01\n",
                                       "date: " + SENTINEL + "\n", 1),
            "run-value": text.replace("run: runs/panel-01\n",
                                      "run: runs/" + SENTINEL + "\n"),
            "dead": entry("result", "v1", extra="run: runs/panel-01\nnote: " + SENTINEL + "\n"),
        }
        shown = 0
        for name, content in [("clean", text)] + sorted(faults.items()):
            folder.put(name + ".txt", content)
            for args in (["check", name + ".txt"],
                         ["check", name + ".txt", "--earlier", "clean.txt"],
                         ["extract", name + ".txt", "v1", "--out", name + ".v1"],
                         ["extract", name + ".txt", "v2", "--out", name + ".v2", "--earlier",
                          "clean.txt"]):
                code, out, err = self.cli(["drafts"] + args)
                shown += len(out) + len(err)
                self.assertNotIn(SENTINEL, out + err)
        self.assertGreater(shown, 1000)
        got = self.extract("clean.txt", "v1", "--out", "own.txt")
        self.assertEqual(got[0], 0)
        with open(folder.path("own.txt"), "rb") as handle:
            self.assertIn(SENTINEL.encode(), handle.read())

    def test_the_sentinel_is_in_no_output_of_a_run_that_cannot_go_ahead(self):
        folder = self.work()
        folder.put("clean.txt", self.draft())
        paths = (["check", os.path.join(SENTINEL, "missing.txt")],
                 ["check", "clean.txt", "--earlier",
                  os.path.join(SENTINEL, "missing.txt")],
                 ["extract", "clean.txt", "v1", "--out",
                  os.path.join(SENTINEL, "missing.txt")])
        cases = (["check", "clean.txt", "--bogus"], ["extract", "clean.txt", "v1"],
                 ["extract", "clean.txt", "v9", "--out", "x.txt"],
                 ["check", "clean.txt", "--earlier", "missing.txt"],
                 ["extract", "clean.txt", "v1", "--out", "clean.txt"])
        for args in cases + paths:
            for run in (self.cli, self.sub):
                code, out, err = run(["drafts"] + args)
                self.assertNotIn(SENTINEL, out + err)


if __name__ == "__main__":
    unittest.main()
