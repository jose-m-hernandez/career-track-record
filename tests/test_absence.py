"""Tests for ``track-record absence`` (spec: docs/specs/absence.md, section 9).

One test per known answer, 9.1 to 9.21; the PDF cases (9.6 and the PDF reads) are in
tests/test_absence_pdf.py. Every fixture is built in a temporary folder at run time, and all of
it is invented. Each test asserts the spec's exact standard output, standard error and exit
status.

The one seam is case 9.16: the spec asks for "a test that makes the tool's own counts
disagree", so that test replaces ``absence._buckets``, the function that counts the four
buckets from the files' statuses, with one that reports a read file too few, and runs the
command in this process.
"""

import hashlib
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

from career_track_record import absence, cli  # noqa: E402

CMD = [sys.executable, "-m", "career_track_record"]
NO_OUTPUT = "cannot run: cannot write output\n"
BASE_SHA = "d0fd170273c50a854e05eac8261ba2fd2a66c506dddbd7121a323648fcdb373a"
TERMS = "# an invented list\norbit-lantern\nvelvet compass\nquill\tword\nlanternfish\n"
HELP = """\
usage: track-record absence DECLARATION

Show that your listed terms appear nowhere in the files you declare.

  -h, --help  show this summary and exit

exit: 0 clean, 1 a term found, 2 DEAD or cannot run
"""
NO_FILES = "files: found %d, read %d, excluded %d, unreadable %d, links not followed %d\n"
# What no output may hold (case 9.17): every entry, matched text, the control phrase, each
# exclusion's reason, the list's name and the names of 9.10, 9.11 and 9.21.
PRIVATE = ("orbit-lantern", "velvet compass", "velvet  compass", "quill", "lanternfish",
           "approved vendors", "drafts kept for the record", "everything under notes",
           "a scan with no text layer", "kept apart", "terms.txt")


def decl_text(label="no-vendor-terms", search=("notes", "summary.txt"),
              place="notes/vendors.txt", control="approved vendors", exclusions=(),
              list_line="list: terms.txt"):
    lines = ["# an invented declaration", "label: " + label]
    if list_line:
        lines.append(list_line)
    lines.append("search:")
    lines.extend("  " + item for item in search)
    lines.append("place: " + place)
    if control is not None:
        lines.append("control: " + control)
    if exclusions:
        lines.append("exclusions:")
        lines.extend("  " + item for item in exclusions)
    return "\n".join(lines) + "\n"


def files_line(found, read, excluded, unreadable, links):
    return NO_FILES % (found, read, excluded, unreadable, links)


def env(extra=None):
    e = dict(os.environ)
    for name in ("BARRED_STRINGS_PATH", "BARRED_STRINGS", "CTR_CONFIG_DIR", "XDG_CONFIG_HOME"):
        e.pop(name, None)
    e["PYTHONPATH"] = SRC
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


class AbsenceCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        self.outputs = []
        self.write("terms.txt", TERMS)
        self.write("notes/vendors.txt", "Approved vendors: Example Corp and Sample Ltd.\n")
        self.write("notes/plan.txt", "The team sharpened its quills before the review.\n")
        self.write("summary.txt", "A quarterly summary of invented work.\n")
        self.write("absence.txt", decl_text())

    def path(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def write(self, rel, text, data=None):
        path = self.path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(text.encode("utf-8") if data is None else data)

    def sha(self, name="absence.txt"):
        with open(self.path(name), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def cli(self, *args, env_extra=None):
        proc = subprocess.run(CMD + ["absence"] + list(args), cwd=self.root,
                              env=env(env_extra), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        got = (proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8"))
        self.outputs.append(got[1] + got[2])
        self.assertNotIn("Traceback", got[2])
        return got

    def run_decl(self, **kwargs):
        """Write absence.txt from decl_text(**kwargs) and run it."""
        self.write("absence.txt", decl_text(**kwargs))
        return self.cli("absence.txt")

    def head(self):
        return "declaration sha256 %s\n" % self.sha()

    # ---------------------------------------------------------------- 9.1

    def test_case_9_1_clean(self):
        """9.1: clean; `quills` is not a hit because entry 3 carries the word flag."""
        self.assertEqual(self.sha(), BASE_SHA)
        expected = (
            "declaration sha256 " + BASE_SHA + "\n" + files_line(3, 3, 0, 0, 0) +
            "CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (0, expected, ""))

    def test_case_9_1_a_folder_place_gives_the_same_output_apart_from_the_hash(self):
        """9.1: with `place: notes` the output is the same apart from the hash line."""
        code, out, err = self.run_decl(place="notes")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, self.head() + files_line(3, 3, 0, 0, 0) +
                         "CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, "
                         "control found\n")

    # ---------------------------------------------------------------- 9.2

    def archive(self):
        self.write("notes/archive/old.txt", "velvet compass\nVelvet  compass\n")

    def test_case_9_2_an_excluded_folder(self):
        """9.2: the hits of an excluded folder are counted and shown as a number."""
        self.archive()
        code, out, err = self.run_decl(exclusions=("notes/archive | drafts kept for the record",))
        expected = (self.head() + "excluded notes/archive: 2 hits in 1 files, 0 not read\n" +
                    files_line(4, 3, 1, 0, 0) +
                    "CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, "
                    "control found; excluding notes/archive\n")
        self.assertEqual((code, out, err), (0, expected, ""))

    def test_case_9_2_without_the_exclusion_the_run_finds_the_hits(self):
        """9.2: without the exclusion, exit 1 and the file's hits."""
        self.archive()
        expected = ("declaration sha256 " + BASE_SHA + "\n"
                    "hit notes/archive/old.txt: 2 hits, entries #2\n" + files_line(4, 4, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 2 hits in 4 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (1, expected, ""))

    # ---------------------------------------------------------------- 9.3 to 9.5

    def test_case_9_3_the_control_is_missing(self):
        """9.3: no file at the place holds the phrase, for a file place and a folder place."""
        self.write("notes/vendors.txt", "Vendors we use: Example Corp.\n")
        for place in ("notes/vendors.txt", "notes"):
            with self.subTest(place=place):
                code, out, err = self.run_decl(place=place)
                self.assertEqual(
                    (code, out, err),
                    (2, self.head() + files_line(3, 3, 0, 0, 0) +
                     "DEAD   no-vendor-terms: control not found at the place\n", ""))

    def test_case_9_4_the_place_is_outside_the_search_set(self):
        """9.4: summary.txt is the only search item."""
        code, out, err = self.run_decl(search=("summary.txt",))
        self.assertEqual(
            (code, out, err),
            (2, self.head() + files_line(1, 1, 0, 0, 0) +
             "DEAD   no-vendor-terms: the place is not in the search set\n", ""))

    def test_case_9_5_the_place_is_inside_an_exclusion(self):
        """9.5: everything under notes is excluded."""
        code, out, err = self.run_decl(exclusions=("notes | everything under notes",))
        self.assertEqual(
            (code, out, err),
            (2, self.head() + files_line(3, 1, 2, 0, 0) +
             "DEAD   no-vendor-terms: the place is inside an exclusion\n", ""))

    # ---------------------------------------------------------------- 9.7 to 9.11

    def test_case_9_7_a_hidden_file(self):
        """9.7: a hidden file is read like any other."""
        self.write("notes/.draft.txt", "a velvet compass\n")
        expected = (self.head() + "hit notes/.draft.txt: 1 hits, entries #2\n" +
                    files_line(4, 4, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 1 hits in 4 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (1, expected, ""))

    def test_case_9_8_a_symbolic_link(self):
        """9.8: a link is counted, not followed."""
        os.symlink("../summary.txt", self.path("notes/link.txt"))
        expected = (self.head() + files_line(4, 3, 0, 0, 1) +
                    "CLEAN  no-vendor-terms: 0 hits in 3 files, 1 links not followed, "
                    "control found\n")
        self.assertEqual(self.cli("absence.txt"), (0, expected, ""))

    def test_case_9_8_a_link_to_a_term_is_not_read(self):
        """9.8: a link is never read, so a term in its target file is not found through it."""
        self.write("elsewhere/target.txt", "an orbit-lantern here\n")
        os.symlink("../elsewhere/target.txt", self.path("notes/link.txt"))
        os.symlink("../elsewhere", self.path("notes/linked-folder"))
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, err), (0, ""))
        self.assertIn(files_line(5, 3, 0, 0, 2), out)

    def test_case_9_9_line_end_hyphens(self):
        """9.9: entry 1 in the hyphen-kept form, entry 4 in the rejoined form."""
        self.write("summary.txt", "the orbit-\nlantern and the lantern-\nfish\n")
        expected = (self.head() + "hit summary.txt: 2 hits, entries #1, #4\n" +
                    files_line(3, 3, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 2 hits in 3 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (1, expected, ""))

    def test_case_9_10_a_term_in_a_file_s_name(self):
        """9.10: shown by its number, 2 in file order, never by its name."""
        self.write("notes/velvet compass.txt", "nothing to see\n")
        expected = ("declaration sha256 " + BASE_SHA + "\n"
                    "hit file #2: 1 hits, entries #2\n" + files_line(4, 4, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 1 hits in 4 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (1, expected, ""))

    def test_case_9_11_a_term_in_a_link_s_name(self):
        """9.11: a link's name is searched; the link is first in file order."""
        os.symlink("../summary.txt", self.path("notes/lanternfish.txt"))
        expected = (self.head() + "hit file #1: 1 hits, entries #4\n" +
                    files_line(4, 3, 0, 0, 1) +
                    "FOUND  no-vendor-terms: 1 hits in 3 files, 1 with hits, 1 links not "
                    "followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (1, expected, ""))

    # ---------------------------------------------------------------- 9.12 to 9.15

    def test_case_9_12_a_comma_in_a_path(self):
        """9.12: a comma in a printed path is written \\x2c."""
        self.archive()
        self.write("notes/drafts, old/old.txt", "nothing here\n")
        code, out, err = self.run_decl(exclusions=("notes/archive | drafts kept for the record",
                                                   "notes/drafts, old | kept apart"))
        expected = (self.head() + "excluded notes/archive: 2 hits in 1 files, 0 not read\n"
                    "excluded notes/drafts\\x2c old: 0 hits in 1 files, 0 not read\n" +
                    files_line(5, 3, 2, 0, 0) +
                    "CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, control "
                    "found; excluding notes/archive, notes/drafts\\x2c old\n")
        self.assertEqual((code, out, err), (0, expected, ""))

    def test_case_9_13_a_file_that_is_not_text(self):
        """9.13: an invented image is read as text and counted as read."""
        self.write("notes/logo.png", "", data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\x01")
        expected = (self.head() + files_line(4, 4, 0, 0, 0) +
                    "CLEAN  no-vendor-terms: 0 hits in 4 files, 0 links not followed, "
                    "control found\n")
        self.assertEqual(self.cli("absence.txt"), (0, expected, ""))

    def test_case_9_14_a_term_that_matches_the_control(self):
        """9.14: a fifth entry `vendors` matches the control phrase."""
        self.write("terms.txt", TERMS + "vendors\n")
        self.assertEqual(self.cli("absence.txt"),
                         (2, "", "cannot run: entry #5 matches the control phrase\n"))

    def test_case_9_14_the_label_matches_an_entry(self):
        """9.14: `-` after `quill` is a boundary character."""
        self.assertEqual(self.run_decl(label="quill-check"),
                         (2, "", "cannot run: the label matches entry #3\n"))

    def test_case_9_15_declaration_problems(self):
        """9.15: each exits 2 with one line and nothing on standard output."""
        cases = [
            ("no reason", dict(exclusions=("notes/archive",)),
             "cannot run: declaration line 10: an exclusion has no reason\n"),
            ("outside the set", dict(exclusions=("elsewhere | a reason",)),
             "cannot run: declaration line 10: an exclusion is not inside the search set\n"),
            ("a space in the label", dict(label="no vendor"),
             "cannot run: declaration line 2: the label holds letters, digits and - only\n"),
            ("no control", dict(control=None), "cannot run: the declaration has no control\n"),
        ]
        for label, kwargs, expected in cases:
            with self.subTest(case=label):
                self.assertEqual(self.run_decl(**kwargs), (2, "", expected))

    def test_case_9_15_every_problem_gets_its_own_line_and_a_key_is_not_echoed(self):
        """9.15: one line each, in line order, then the missing keys; an unknown key's text
        is not repeated, since it could be a term or the control phrase."""
        self.write("absence.txt", "approved vendors: x\nlabel: a b\nlabel: c\n")
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, (
            "cannot run: declaration line 1: unknown key\n"
            "cannot run: declaration line 2: the label holds letters, digits and - only\n"
            "cannot run: declaration line 3: the key label is given twice\n"
            "cannot run: the declaration has no search\n"
            "cannot run: the declaration has no place\n"
            "cannot run: the declaration has no control\n"))

    # ---------------------------------------------------------------- 9.16

    def test_case_9_16_counts_that_disagree(self):
        """9.16: the tool's own counts disagree: cannot run, nothing on standard output."""
        out, err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8"), \
            io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with mock.patch.object(absence, "_buckets", lambda found: (2, 0, 0, 0)), \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = cli.main(["absence", self.path("absence.txt")], environ={})
            out.flush()
            err.flush()
        self.assertEqual(code, 2)
        self.assertEqual(out.buffer.getvalue(), b"")
        self.assertEqual(err.buffer.getvalue(), (
            "cannot run: the files do not reconcile: found 3, read 2, excluded 0, "
            "unreadable 0, links not followed 0\n").encode("utf-8"))

    # ---------------------------------------------------------------- 9.18, 9.19

    def closed(self, fd):
        redirect = ">&-" if fd == 1 else "2>&-"
        proc = subprocess.run(
            ["/bin/sh", "-c", 'exec "$0" "$@" ' + redirect] + CMD + ["absence", "absence.txt"],
            cwd=self.root, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")

    def test_case_9_18_closed_standard_output(self):
        """9.18: exit 2 and one line."""
        self.assertEqual(self.closed(1), (2, "", NO_OUTPUT))

    def test_case_9_18_a_broken_pipe(self):
        """9.18: a reader that is already gone."""
        reader, writer = os.pipe()
        os.close(reader)
        try:
            proc = subprocess.run(CMD + ["absence", "absence.txt"], cwd=self.root, env=env(),
                                  stdin=subprocess.DEVNULL, stdout=writer,
                                  stderr=subprocess.PIPE)
        finally:
            os.close(writer)
        self.assertEqual((proc.returncode, proc.stderr.decode("utf-8")), (2, NO_OUTPUT))

    def test_case_9_18_closed_standard_error_changes_no_exit_status(self):
        """9.18: a clean run stays 0; a cannot-run stays 2."""
        code, out, _err = self.cli("absence.txt")
        self.assertEqual(self.closed(2), (code, out, ""))
        self.write("absence.txt", decl_text(label="quill-check"))
        self.assertEqual(self.closed(2), (2, "", ""))

    def test_case_9_18_a_full_disk(self):
        """9.18: a write that fails exits 2 with the one line, in this process."""
        class Full(object):
            class buffer(object):
                @staticmethod
                def write(data):
                    raise OSError(28, "No space left on device")

                @staticmethod
                def flush():
                    pass

            @staticmethod
            def write(text):
                raise OSError(28, "No space left on device")

            @staticmethod
            def flush():
                pass

        err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with mock.patch.object(sys, "stdout", Full()), mock.patch.object(sys, "stderr", err):
            code = cli.main(["absence", self.path("absence.txt")], environ={})
            err.flush()
        self.assertEqual(code, 2)
        self.assertEqual(err.buffer.getvalue(), NO_OUTPUT.encode("utf-8"))

    def test_case_9_19_help(self):
        """9.19: -h and --help write the summary, read no file, and win over everything."""
        for args in (["-h"], ["--help"], ["--help", "a", "b"], ["--bogus", "-h"],
                     ["missing.txt", "--help"]):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args), (0, HELP, ""))
        self.assertEqual(self.cli("--", "--help"),
                         (2, "", "cannot run: cannot read the declaration\n"))

    def test_case_9_19_the_help_text_is_the_spec_s(self):
        """9.19: the same bytes as the signed block's fenced summary."""
        with open(os.path.join(ROOT, "docs", "specs", "absence.md"), encoding="utf-8") as handle:
            spec = handle.read()
        marker = "writes exactly this, followed by a line break:\n\n```text\n"
        start = spec.index(marker) + len(marker)
        self.assertEqual(spec[start:spec.index("```", start)], HELP)
        self.assertEqual(cli._ABSENCE_HELP, HELP)

    # ---------------------------------------------------------------- 9.20, 9.21

    def test_case_9_20_a_line_end_soft_hyphen_in_a_text_file(self):
        """9.20: the soft hyphen ends a line after a word character; entry 4 is found."""
        self.write("summary.txt", "the lantern" + chr(0xAD) + "\nfish shop\n")
        expected = (self.head() + "hit summary.txt: 1 hits, entries #4\n" +
                    files_line(3, 3, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 1 hits in 3 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (1, expected, ""))

    def test_case_9_21_two_entries_in_one_name(self):
        """9.21: one hit for each entry that matches the name."""
        self.write("notes/velvet compass lanternfish.txt", "nothing to see\n")
        expected = ("declaration sha256 " + BASE_SHA + "\n"
                    "hit file #2: 2 hits, entries #2, #4\n" + files_line(4, 4, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 2 hits in 4 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual(self.cli("absence.txt"), (1, expected, ""))

    def test_case_9_21_a_name_that_holds_one_entry_twice(self):
        """9.21: `notes/velvet compass velvet compass.txt` gives one hit."""
        self.write("notes/velvet compass velvet compass.txt", "nothing to see\n")
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("hit file #2: 1 hits, entries #2\n", out)

    # ---------------------------------------------------------------- 9.17

    def test_case_9_17_nothing_private_is_printed(self):
        """9.17: over every case above, nothing private is on standard output or error."""
        for name in sorted(dir(type(self))):
            if name.startswith("test_case_9_") and not name.startswith("test_case_9_17"):
                with self.subTest(case=name):
                    case = type(self)(name)
                    case.setUp()
                    try:
                        getattr(case, name)()
                        self.outputs.extend(case.outputs)
                    finally:
                        case.doCleanups()
        self.assertGreater(len(self.outputs), 30)
        for text in self.outputs:
            for secret in PRIVATE:
                self.assertNotIn(secret, text.lower())

    # ---------------------------------------------------------------- more of the spec

    def test_the_declaration_s_bom_is_dropped_but_hashed(self):
        """3.1: a byte-order mark is dropped; the hash covers the file's bytes."""
        data = b"\xef\xbb\xbf" + decl_text().encode("utf-8")
        self.write("absence.txt", "", data=data)
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines()[0],
                         "declaration sha256 " + hashlib.sha256(data).hexdigest())

    def test_a_declaration_that_cannot_be_used(self):
        """7: not readable, not a regular file, not UTF-8; its name is not printed."""
        self.assertEqual(self.cli("nothing.txt"),
                         (2, "", "cannot run: cannot read the declaration\n"))
        self.assertEqual(self.cli("notes"), (2, "", "cannot run: cannot read the declaration\n"))
        self.write("bad.txt", "", data=b"label: \xff\n")
        self.assertEqual(self.cli("bad.txt"),
                         (2, "", "cannot run: the declaration is not valid UTF-8\n"))

    def test_the_command_line_messages(self):
        """3.0 and 7."""
        self.assertEqual(self.cli(), (2, "", "cannot run: absence needs a DECLARATION file\n"))
        self.assertEqual(self.cli("a.txt", "b.txt"),
                         (2, "", "cannot run: absence takes one DECLARATION file, not "
                                 "several\n"))
        self.assertEqual(self.cli("--bogus=1", "absence.txt"),
                         (2, "", "cannot run: unknown option --bogus\n"))
        self.assertEqual(self.cli("--", "-"),
                         (2, "", "cannot run: cannot read the declaration\n"))

    def test_the_list_comes_from_the_environment_when_the_declaration_has_no_list_key(self):
        """3.2: the variable names the list; unset or empty counts as absent."""
        self.write("absence.txt", decl_text(list_line=""))
        code, out, err = self.cli("absence.txt", env_extra={
            "BARRED_STRINGS_PATH": self.path("terms.txt")})
        self.assertEqual((code, err), (0, ""))
        self.assertIn("CLEAN  no-vendor-terms", out)
        for value in (None, ""):
            with self.subTest(value=value):
                extra = {} if value is None else {"BARRED_STRINGS_PATH": value}
                self.assertEqual(
                    self.cli("absence.txt", env_extra=extra),
                    (2, "", "cannot run: no list (give --list or set BARRED_STRINGS_PATH)\n"))

    def test_a_list_that_cannot_be_used_says_barred_s_message(self):
        """3.2 and 7: barred.md section 7, case 3."""
        self.write("terms.txt", "# only a comment\n")
        self.assertEqual(self.cli("absence.txt"),
                         (2, "", "cannot run: the list has no entries\n"))
        os.remove(self.path("terms.txt"))
        self.assertEqual(self.cli("absence.txt"),
                         (2, "", "cannot run: the list file cannot be read\n"))

    def test_the_control_phrase_must_not_be_empty_once_prepared(self):
        """7: a control of one zero-width space is empty once prepared."""
        self.assertEqual(self.run_decl(control=chr(0x200B)),
                         (2, "", "cannot run: the control phrase is empty\n"))

    def test_a_file_reached_through_two_search_items_is_found_once(self):
        """3.3."""
        code, out, err = self.run_decl(search=("notes", "notes/plan.txt", "./notes",
                                               "summary.txt"))
        self.assertEqual((code, err), (0, ""))
        self.assertIn(files_line(3, 3, 0, 0, 0), out)

    def test_a_missing_search_item_is_one_file_found_and_unreadable(self):
        """3.3: the run is DEAD."""
        code, out, err = self.run_decl(search=("notes", "summary.txt", "gone.txt"))
        self.assertEqual(
            (code, out, err),
            (2, self.head() + files_line(4, 3, 0, 1, 0) +
             "DEAD   no-vendor-terms: 1 unreadable files\n", ""))

    def test_the_order_is_the_order_of_the_search_items_then_code_points(self):
        """3.3: `a.txt` comes before `a/b.txt` in code-point order of their paths."""
        self.write("notes/a/b.txt", "inside\n")
        self.write("notes/a.txt", "beside orbit-lantern\n")
        self.write("notes/b.txt", "beside orbit-lantern\n")
        os.symlink("a", self.path("notes/ab"))
        code, out, err = self.run_decl(search=("summary.txt", "notes"))
        self.assertEqual((code, err), (1, ""))
        hits = [line for line in out.splitlines() if line.startswith("hit ")]
        self.assertEqual(hits, ["hit notes/a.txt: 1 hits, entries #1",
                                "hit notes/b.txt: 1 hits, entries #1"])

    def test_a_folder_in_the_path_whose_name_matches_hides_every_name_below_it(self):
        """4 and 6: the path as written, folders included, is checked and shown by number."""
        self.write("notes/orbit-lantern/one.txt", "plain\n")
        self.write("notes/orbit-lantern/two.txt", "plain\n")
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("hit file #1: 1 hits, entries #1\nhit file #2: 1 hits, entries #1\n", out)
        self.assertNotIn("orbit-lantern", out)

    def test_an_excluded_path_whose_name_matches_is_shown_by_its_position(self):
        """6: `exclusion #<i>` is the position among the exclusions, in both places."""
        self.write("notes/velvet compass/old.txt", "nothing\n")
        code, out, err = self.run_decl(exclusions=(
            "notes/archive | one", "notes/velvet compass | two"))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("excluded exclusion #2: 1 hits in 1 files, 0 not read\n", out)
        self.assertTrue(out.endswith("control found; excluding notes/archive, "
                                     "exclusion #2\n"), out)

    def test_the_list_among_the_files_is_shown_by_number_not_by_its_path(self):
        """6: the list's path is never printed, even when the list is searched."""
        code, out, err = self.run_decl(search=("notes", "summary.txt", "terms.txt"))
        self.assertEqual((code, err), (1, ""))
        self.assertIn("hit file #4: ", out)
        self.assertNotIn("terms.txt", out)

    def test_an_excluded_link_is_a_link_not_followed_and_its_name_counts_there(self):
        """3.3 and 3.5: a link inside an exclusion is in the links bucket, not excluded."""
        self.archive()
        os.symlink("../../summary.txt", self.path("notes/archive/lanternfish.txt"))
        code, out, err = self.run_decl(exclusions=("notes/archive | kept",))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("excluded notes/archive: 3 hits in 1 files, 0 not read\n", out)
        self.assertIn(files_line(5, 3, 1, 0, 1), out)

    def linked_parent(self):
        """A real folder `elsewhere` and a link `sub` to it; `old.txt` holds a term."""
        self.write("elsewhere/old.txt", "beside orbit-lantern\n")
        self.write("elsewhere/vendors.txt", "Approved vendors: Example Corp.\n")
        os.symlink("elsewhere", self.path("sub"))

    def test_a_search_item_through_a_linked_parent_is_a_link_not_followed(self):
        """3.3: a link in any component of the written path is a link not followed."""
        self.linked_parent()
        code, out, err = self.run_decl(search=("notes", "summary.txt", "sub/old.txt"))
        expected = (self.head() + files_line(4, 3, 0, 0, 1) +
                    "CLEAN  no-vendor-terms: 0 hits in 3 files, 1 links not followed, "
                    "control found\n")
        self.assertEqual((code, out, err), (0, expected, ""))

    def test_a_search_item_through_a_linked_parent_has_its_name_searched(self):
        """3.3 and 4: the link is not read, but its written name is."""
        self.linked_parent()
        os.symlink("elsewhere", self.path("lanternfish"))
        code, out, err = self.run_decl(search=("notes", "summary.txt", "lanternfish/old.txt"))
        expected = (self.head() + "hit file #4: 1 hits, entries #4\n" +
                    files_line(4, 3, 0, 0, 1) +
                    "FOUND  no-vendor-terms: 1 hits in 3 files, 1 with hits, 1 links not "
                    "followed, control found\n")
        self.assertEqual((code, out, err), (1, expected, ""))

    def test_a_place_through_a_linked_parent_is_not_read(self):
        """3.3 and 3.4: the control is not found through a link, so the run is DEAD."""
        self.linked_parent()
        code, out, err = self.run_decl(search=("notes", "summary.txt", "sub/vendors.txt"),
                                       place="sub/vendors.txt")
        expected = (self.head() + files_line(4, 3, 0, 0, 1) +
                    "DEAD   no-vendor-terms: control not found at the place\n")
        self.assertEqual((code, out, err), (2, expected, ""))

    def test_an_exclusion_through_a_linked_parent_is_a_link_not_followed(self):
        """3.3 and 3.5: the item is in the links bucket, not read, not excluded."""
        self.linked_parent()
        code, out, err = self.run_decl(search=("notes", "summary.txt", "sub/old.txt"),
                                       exclusions=("sub/old.txt | kept apart",))
        expected = (self.head() + "excluded sub/old.txt: 0 hits in 0 files, 0 not read\n" +
                    files_line(4, 3, 0, 0, 1) +
                    "CLEAN  no-vendor-terms: 0 hits in 3 files, 1 links not followed, "
                    "control found; excluding sub/old.txt\n")
        self.assertEqual((code, out, err), (0, expected, ""))

    def test_an_absolute_path_through_a_link_is_a_link_not_followed(self):
        """3.3: every component of an absolute path counts, a system link included."""
        self.linked_parent()
        written = os.path.join(self.root, "sub", "old.txt")
        code, out, err = self.run_decl(search=("notes", "summary.txt", written))
        self.assertEqual((code, err), (0, ""))
        self.assertIn(files_line(4, 3, 0, 0, 1), out)

    def test_a_plain_item_beside_a_linked_parent_is_read(self):
        """3.3: the same file by its real path is read and its term found."""
        self.linked_parent()
        code, out, err = self.run_decl(search=("notes", "summary.txt", "elsewhere/old.txt"))
        expected = (self.head() + "hit elsewhere/old.txt: 1 hits, entries #1\n" +
                    files_line(4, 4, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 1 hits in 4 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual((code, out, err), (1, expected, ""))

    def test_a_file_that_is_not_regular_is_unreadable_and_is_never_opened(self):
        """3.3: a named pipe would block a read; it is unreadable at once."""
        os.mkfifo(self.path("notes/pipe"))
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, err), (2, ""))
        self.assertIn(files_line(4, 3, 0, 1, 0), out)
        self.assertTrue(out.endswith("DEAD   no-vendor-terms: 1 unreadable files\n"))

    @unittest.skipIf(os.geteuid() == 0, "a file cannot be made unreadable for root")
    def test_an_unreadable_file_is_dead_unless_it_is_excluded(self):
        """3.3 and 3.5: the same file, with and without an exclusion."""
        self.write("notes/locked.txt", "orbit-lantern\n")
        os.chmod(self.path("notes/locked.txt"), 0)
        self.addCleanup(os.chmod, self.path("notes/locked.txt"), stat.S_IRUSR | stat.S_IWUSR)
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, err), (2, ""))
        self.assertTrue(out.endswith("DEAD   no-vendor-terms: 1 unreadable files\n"), out)
        self.assertNotIn("hit ", out)
        code, out, err = self.run_decl(exclusions=("notes/locked.txt | a locked file",))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("excluded notes/locked.txt: 0 hits in 1 files, 1 not read\n", out)
        self.assertIn(files_line(4, 3, 1, 0, 0), out)

    @unittest.skipIf(os.geteuid() == 0, "a folder cannot be made unlistable for root")
    def test_a_folder_that_cannot_be_listed_is_unreadable(self):
        """3.3 (the spec is silent on a folder that cannot be listed; it must not pass as
        empty, so it is one unreadable path)."""
        self.write("notes/sealed/inside.txt", "orbit-lantern\n")
        os.chmod(self.path("notes/sealed"), 0)
        self.addCleanup(os.chmod, self.path("notes/sealed"), stat.S_IRWXU)
        code, out, err = self.cli("absence.txt")
        self.assertEqual((code, err), (2, ""))
        self.assertIn(files_line(4, 3, 0, 1, 0), out)

    def test_a_search_set_of_links_only_holds_no_file(self):
        """5, reason 1."""
        os.symlink("summary.txt", self.path("only-link"))
        code, out, err = self.run_decl(search=("only-link",), place="only-link")
        self.assertEqual(
            (code, out, err),
            (2, self.head() + files_line(1, 0, 0, 0, 1) +
             "DEAD   no-vendor-terms: no file in the search set\n", ""))

    def test_the_place_is_compared_as_written_after_dots_are_resolved(self):
        """3.3: `notes/../notes/vendors.txt` is inside `notes`; no link is followed."""
        code, out, err = self.run_decl(place="notes/../notes/vendors.txt")
        self.assertEqual((code, err), (0, ""))
        os.symlink("notes", self.path("alias"))
        code, out, err = self.run_decl(place="alias/vendors.txt")
        self.assertIn("DEAD   no-vendor-terms: the place is not in the search set\n", out)

    def test_a_declaration_in_another_folder_reads_its_paths_from_its_own_folder(self):
        """3.1: paths are relative to the declaration's folder, and printed as written."""
        os.makedirs(self.path("sub"))
        self.write("sub/absence.txt", decl_text(
            search=("../notes", "../summary.txt"), place="../notes/vendors.txt",
            list_line="list: ../terms.txt"))
        proc = subprocess.run(CMD + ["absence", "sub/absence.txt"], cwd=self.root, env=env(),
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(files_line(3, 3, 0, 0, 0), proc.stdout.decode("utf-8"))

    def test_a_folder_search_item_prints_the_path_as_written_then_a_slash(self):
        """3.1: a file found in a folder is the folder's path, `/`, then its path inside."""
        self.write("notes/archive/old.txt", "an orbit-lantern\n")
        code, out, err = self.run_decl(search=("./notes/", "summary.txt"))
        self.assertEqual((code, err), (1, ""))
        self.assertIn("hit ./notes//archive/old.txt: 1 hits, entries #1\n", out)

    # ---------------------------------------------------------------- 3.4 and 6 (fix round)

    def dead_no_control(self, place):
        return (2, self.head() + files_line(3, 3, 0, 0, 0) +
                "DEAD   no-vendor-terms: control not found at the place\n", "")

    def test_3_4_a_control_only_outside_a_folder_place_is_dead(self):
        """3.4: the control is in summary.txt, outside the place `notes`: DEAD."""
        self.write("notes/vendors.txt", "Vendors we use: Example Corp.\n")
        self.write("summary.txt", "Approved vendors: Example Corp.\n")
        self.assertEqual(self.run_decl(place="notes"), self.dead_no_control("notes"))

    def test_3_4_a_control_only_outside_a_file_place_is_dead(self):
        """3.4: the control is in summary.txt, outside the place `notes/vendors.txt`: DEAD."""
        self.write("notes/vendors.txt", "Vendors we use: Example Corp.\n")
        self.write("summary.txt", "Approved vendors: Example Corp.\n")
        self.assertEqual(self.run_decl(place="notes/vendors.txt"),
                         self.dead_no_control("notes/vendors.txt"))

    def test_3_4_a_control_in_a_sibling_of_a_file_place_is_dead(self):
        """3.4: the control is in notes/plan.txt, a sibling of the place file: DEAD."""
        self.write("notes/vendors.txt", "Vendors we use: Example Corp.\n")
        self.write("notes/plan.txt", "Approved vendors: Example Corp.\n")
        self.assertEqual(self.run_decl(place="notes/vendors.txt"),
                         self.dead_no_control("notes/vendors.txt"))

    def test_3_4_a_control_in_another_file_inside_a_folder_place_is_clean(self):
        """3.4: the positive twin; the control is in notes/plan.txt, inside the place `notes`."""
        self.write("notes/vendors.txt", "Vendors we use: Example Corp.\n")
        self.write("notes/plan.txt", "Approved vendors: Example Corp.\n")
        code, out, err = self.run_decl(place="notes")
        expected = (self.head() + files_line(3, 3, 0, 0, 0) +
                    "CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, "
                    "control found\n")
        self.assertEqual((code, out, err), (0, expected, ""))

    # A name is matched as written, as barred prints it, and as this command prints it (4).

    def name_list_case(self, filename, hit_entry):
        """Write the invented list, create notes/<filename> and run; expect file #1 as a hit."""
        bs = "\\"
        self.write("terms.txt", "# an invented list\nember" + bs + "x2cglass\nember" + bs +
                   "tglass\nember," + bs + "tglass\n")
        self.write("notes/" + filename, "nothing to see\n")
        code, out, err = self.run_decl()
        expected = (self.head() + "hit file #1: 1 hits, entries #%d\n" % hit_entry +
                    files_line(4, 4, 0, 0, 0) +
                    "FOUND  no-vendor-terms: 1 hits in 4 files, 1 with hits, 0 links not "
                    "followed, control found\n")
        self.assertEqual((code, out, err), (1, expected, ""))
        for text in (filename[:-4], "ember" + bs + "x2cglass", "ember" + bs + "tglass",
                     "ember," + bs + "tglass"):
            self.assertNotIn(text, out + err)

    def test_4_a_name_is_matched_in_the_form_this_command_prints(self):
        """4: `ember,glass.txt` does not hold entry 1's text as written; printed it does."""
        self.name_list_case("ember,glass.txt", 1)

    def test_4_a_name_is_matched_in_the_form_barred_prints(self):
        """4 and 6: a tab in a name is printed `\\t`, which is entry 2's text."""
        try:
            self.name_list_case("ember\tglass.txt", 2)
        except OSError as exc:
            self.skipTest("this filesystem refuses a tab in a name: %s" % exc)

    def test_4_a_name_is_matched_in_the_form_barred_prints_before_a_comma_is_escaped(self):
        """4 and 6: `ember,<TAB>glass.txt` is printed `ember,\\tglass` by barred (entry 3's
        text) and `ember\\x2c\\tglass` by this command; only barred's form matches entry 3."""
        try:
            self.name_list_case("ember,\tglass.txt", 3)
        except OSError as exc:
            self.skipTest("this filesystem refuses a tab in a name: %s" % exc)


if __name__ == "__main__":
    unittest.main()
