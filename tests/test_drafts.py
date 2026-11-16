"""Tests for ``track-record drafts``: the known answers, each rule's planted fault, the sha256
of a version and the self-test. Every draft file, version and note here is invented.

The known answers are section 10 of docs/specs/drafts.md, read from the spec file itself.
Tests of section 10 are named ``test_10_`` and quote the bullet they cover. A test that needs a
file name as printed copies the fixtures into a temporary folder and works from there. The
sentinel check and the traceback check of ``RecordCase.tearDown`` apply to every run these
tests make. Invisible and control characters are written with chr(), never raw.
"""

import hashlib
import os
import shutil
import sys
import unittest
import unittest.mock

from tests import test_record_check as base

ROOT = base.ROOT
SPEC = os.path.join(ROOT, "docs", "specs", "drafts.md")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "drafts")

from career_track_record import cli, drafts  # noqa: E402

NAMES = ("letter.txt", "letter-before.txt", "letter-edited.txt")
NO_EARLIER = "no earlier copy given"
NO_EARLIER_LINE = "no earlier copy given: rule 8 not applied\n"
V3_SHA = "e9db1dc84b01be6dbafe216e3dd033b3ecb1c83db3143a2925d3381348bfe6b8"
OK_LINE = ("OK    letter.txt: versions 3, parents resolved 3, results 1, run folders found 1, "
           "send entries 1; send copy v3; earlier copy 259 bytes, file 600 bytes")
FAIL_EDITED = ("FAIL  letter-edited.txt: versions 2, parents resolved 2, results 1, run folders "
               "found 1, send entries 0; faults 1; earlier copy 259 bytes, file 359 bytes\n"
               "letter-edited.txt:10: differs from the earlier copy\n")


def text_of(name):
    return base.read(os.path.join(FIXTURES, name))


def lines_of(text):
    """The lines of a text whose every line ends with LF."""
    return text.split("\n")[:-1]


def joined(lines):
    return "\n".join(lines) + "\n"


def counts(v, p, r, f, s):
    return ("versions %d, parents resolved %d, results %d, run folders found %d, "
            "send entries %d" % (v, p, r, f, s))


def fail(name, c, faults, earlier=NO_EARLIER):
    return "FAIL  %s: %s; faults %d; %s\n" % (name, c, faults, earlier)


def finding_lines(name, found):
    return "".join("%s:%d: %s\n" % (name, line, text) if line is not None
                   else "%s: %s\n" % (name, text) for line, text in found)


def digests(text):
    """{id: sha256 of the version's bytes} for the accepted versions of a draft file's text."""
    draft = drafts.read_draft(drafts.split_lines(text))
    return dict((s.ident, hashlib.sha256(drafts.version_bytes(s)).hexdigest())
                for s in draft.accepted() if s.kind == "version")


def version(ident, parent="none", date="2026-01-01", change="first", text="Words.\n",
            extra=""):
    return ("## %s\nparent: %s\ndate: %s\nchange: %s\n%stext:\n%s"
            % (ident, parent, date, change, extra, text))


def entry(kind, ident, date="2026-01-01", extra=""):
    return "## %s\nversion: %s\ndate: %s\n%s" % (kind, ident, date, extra)


class DraftsCase(base.RecordCase):
    def work(self, files=NAMES):
        """A temporary folder, with the fixtures copied into it and its run folder made, that
        this test works from."""
        folder = self.folder()
        for name in files:
            shutil.copy(os.path.join(FIXTURES, name), folder.path(name))
        os.makedirs(folder.path("runs/panel-01"))
        old = os.getcwd()
        os.chdir(folder.dir)
        self.addCleanup(os.chdir, old)
        return folder

    def check(self, *args):
        return self.cli(["drafts", "check"] + list(args))

    def extract(self, *args):
        return self.cli(["drafts", "extract"] + list(args))

    def planted(self, lines, c, found, earlier=None, name="letter.txt"):
        """Write ``lines`` as letter.txt, check it, and expect the FAIL line and findings."""
        folder = self.work()
        folder.put(name, joined(lines))
        args = [name] if earlier is None else [name, "--earlier", earlier]
        code, out, err = self.check(*args)
        shown = NO_EARLIER if earlier is None else None
        if shown is None:
            data = folder.path(earlier)
            with open(data, "rb") as handle:
                before = len(handle.read())
            with open(folder.path(name), "rb") as handle:
                now = len(handle.read())
            shown = "earlier copy %d bytes, file %d bytes" % (before, now)
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail(name, c, len(found), shown) + finding_lines(name, found))
        return folder


class FixtureTest(DraftsCase):
    def test_10_the_fixtures_are_the_specs_block_and_cuts(self):
        """The fixtures are invented: a letter to Example Corp in three versions."""
        spec = base.read(SPEC)
        block = base.fenced_after(spec, "`letter.txt`:")
        letter = lines_of(block)
        self.assertEqual(text_of("letter.txt"), block)
        self.assertEqual(text_of("letter-before.txt"), joined(letter[:17]))
        middle = ["## result", "version: v1", "date: 2026-03-03", "run: runs/panel-01",
                  "note: two readers found the opening slow", ""]
        self.assertEqual(text_of("letter-edited.txt"), joined(letter[:9] + middle + letter[9:17]))

    def test_10_the_fixtures_have_the_specs_sizes_and_line_counts(self):
        """Every line ends with LF, so the file is 37 lines and 600 bytes."""
        for name, lines, size in (("letter.txt", 37, 600), ("letter-before.txt", 17, 259),
                                  ("letter-edited.txt", 23, 359)):
            with self.subTest(name):
                with open(os.path.join(FIXTURES, name), "rb") as handle:
                    data = handle.read()
                self.assertEqual((data.count(b"\n"), len(data)), (lines, size))
                self.assertFalse(data.endswith(b"\n\n"))

    def test_10_the_specs_sha256_is_the_value_on_v3s_line(self):
        """Its sha256 is the value on v3's `sha256:` line."""
        self.assertIn("sha256: " + V3_SHA + "\n", text_of("letter.txt"))
        self.assertEqual(digests(text_of("letter.txt"))["v3"], V3_SHA)


class KnownAnswerTest(DraftsCase):
    def test_10_k1_check_with_an_earlier_copy_is_ok(self):
        """`drafts check letter.txt --earlier letter-before.txt` writes the line below and
        exits 0."""
        self.work()
        self.assertEqual(self.check("letter.txt", "--earlier", "letter-before.txt"),
                         (0, OK_LINE + "\n", ""))
        spec = base.fenced_after(base.read(SPEC), "writes the line below and exits `0`:")
        self.assertEqual(spec, OK_LINE + "\n")

    def test_10_k2_without_an_earlier_copy_the_line_says_so(self):
        """Without `--earlier`, the line ends `send copy v3; no earlier copy given`."""
        self.work()
        code, out, err = self.check("letter.txt")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.endswith("; send copy v3; no earlier copy given\n"))
        self.assertEqual(out.count("\n"), 1)

    def test_10_k3_an_edited_file_fails(self):
        """`drafts check letter-edited.txt --earlier letter-before.txt` writes these lines and
        exits 1."""
        self.work()
        self.assertEqual(self.check("letter-edited.txt", "--earlier", "letter-before.txt"),
                         (1, FAIL_EDITED, ""))
        spec = base.fenced_after(base.read(SPEC), "writes these lines and exits `1`:")
        self.assertEqual(spec, FAIL_EDITED)

    def test_10_k4_extract_with_an_earlier_copy_writes_the_bytes_only(self):
        """`drafts extract letter.txt v3 --out v3.txt --earlier letter-before.txt` writes the
        66 bytes of v3's text to `v3.txt`; it writes nothing to standard output or standard
        error, and exits 0."""
        folder = self.work()
        self.assertEqual(self.extract("letter.txt", "v3", "--out", "v3.txt", "--earlier",
                                      "letter-before.txt"), (0, "", ""))
        with open(folder.path("v3.txt"), "rb") as handle:
            data = handle.read()
        self.assertEqual(len(data), 66)
        self.assertEqual(hashlib.sha256(data).hexdigest(), V3_SHA)

    def test_10_k5_extract_without_an_earlier_copy_says_rule_8_was_not_applied(self):
        """Without `--earlier`, it writes the same bytes, writes `no earlier copy given: rule 8
        not applied` to standard error, and exits 0."""
        folder = self.work()
        self.assertEqual(self.extract("letter.txt", "v3", "--out", "v3.txt"),
                         (0, "", NO_EARLIER_LINE))
        with open(folder.path("v3.txt"), "rb") as handle:
            self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), V3_SHA)

    def test_10_k6_extract_from_an_edited_file_writes_no_file(self):
        """`drafts extract letter-edited.txt v2 --out v2.txt --earlier letter-before.txt`
        writes no file, writes the two lines above to standard error and exits 1."""
        folder = self.work()
        self.assertEqual(self.extract("letter-edited.txt", "v2", "--out", "v2.txt", "--earlier",
                                      "letter-before.txt"), (1, "", FAIL_EDITED))
        self.assertFalse(os.path.lexists(folder.path("v2.txt")))

    def test_10_the_known_answers_are_the_same_in_a_process_of_their_own(self):
        """A command run as a user runs it."""
        self.work()
        self.assertEqual(self.sub(["drafts", "check", "letter.txt", "--earlier",
                                   "letter-before.txt"]), (0, OK_LINE + "\n", ""))
        self.assertEqual(self.sub(["drafts", "check", "letter-edited.txt", "--earlier",
                                   "letter-before.txt"]), (1, FAIL_EDITED, ""))


class FormFaultTest(DraftsCase):
    """Rule 1. The lines of letter.txt: v1 at 1, v2 at 10, the result at 19, v3 at 25 and the
    send entry at 35."""

    def letter(self):
        return lines_of(text_of("letter.txt"))

    def test_10_form_a_stray_header_line_inside_a_text(self):
        """form: a stray `## v4` line inside a text"""
        lines = self.letter()
        lines[15] = "## v4"
        self.planted(lines, counts(3, 3, 1, 1, 1), [(16, "no parent line after the header")])

    def test_10_form_an_unknown_key(self):
        """form: an unknown key"""
        lines = self.letter()
        lines.insert(28, "colour: blue")
        self.planted(lines, counts(2, 2, 1, 1, 1),
                     [(29, "unknown key"), (37, "version not found")])

    def test_10_form_keys_out_of_order(self):
        """form: keys out of order"""
        lines = self.letter()
        lines[11], lines[12] = lines[12], lines[11]
        self.planted(lines, counts(2, 1, 1, 1, 1),
                     [(13, "key out of order"), (26, "parent not found")])

    def test_10_form_a_version_with_no_text_line(self):
        """form: a version with no `text:` line (R2: the finding with the smallest line)"""
        lines = self.letter()
        del lines[4]
        self.planted(lines, counts(2, 1, 1, 1, 1),
                     [(1, "no text line"), (10, "first version has a parent"),
                      (19, "version not found")])

    def test_10_form_a_version_whose_text_is_all_blank(self):
        """form: a version whose text is all blank"""
        lines = self.letter()
        lines[30:33] = ["", " \t", ""]
        self.planted(lines, counts(2, 2, 1, 1, 1),
                     [(25, "empty text"), (36, "version not found")])

    def test_10_form_a_line_after_an_entry(self):
        """form: a line after an entry"""
        lines = self.letter() + ["", "stray words"]
        self.planted(lines, counts(3, 3, 1, 1, 0), [(39, "line after an entry")])

    def test_10_form_a_line_before_the_first_section(self):
        """form: a line before the first section"""
        self.planted(["stray words"] + self.letter(), counts(3, 3, 1, 1, 1),
                     [(1, "line before the first section")])

    def test_10_a_header_with_no_first_key_line(self):
        """A header must be followed by its first key (spec 3.1, rule 1.1)."""
        lines = self.letter()
        lines.insert(19, "")
        self.planted(lines, counts(3, 3, 0, 0, 1),
                     [(19, "no version line after the header")])

    def test_10_a_required_key_that_is_missing(self):
        """rule 1.4: `no <key> line`, at the header's line"""
        lines = self.letter()
        del lines[2]
        self.planted(lines, counts(2, 1, 1, 1, 1),
                     [(1, "no date line"), (10, "first version has a parent"),
                      (19, "version not found")])

    def test_10_a_key_that_is_repeated(self):
        """rule 1.3: a key that is repeated"""
        lines = self.letter()
        lines.insert(3, "date: 2026-03-02")
        self.planted(lines, counts(2, 1, 1, 1, 1),
                     [(4, "key out of order"), (12, "first version has a parent"),
                      (21, "version not found")])


class RuleFaultTest(DraftsCase):
    def letter(self):
        return lines_of(text_of("letter.txt"))

    def test_10_ids_a_repeated_id(self):
        """ids: a repeated id"""
        lines = self.letter()
        lines[24] = "## v2"
        lines[25] = "parent: v1"
        lines[35] = "version: v2"
        self.planted(lines, counts(3, 3, 1, 1, 1), [(25, "repeated id, first on line 10")])

    def test_10_ids_ids_out_of_order(self):
        """ids: ids out of order"""
        lines = self.letter()
        lines[24] = "## v0"
        lines[35] = "version: v0"
        self.planted(lines, counts(3, 3, 1, 1, 1), [(25, "id out of order, line 10")])

    def test_10_parents_a_first_version_with_a_parent(self):
        """parents: a first version with a parent"""
        lines = self.letter()
        lines[1] = "parent: v1"
        self.planted(lines, counts(3, 2, 1, 1, 1), [(2, "first version has a parent")])

    def test_10_parents_a_parent_that_is_the_version_itself(self):
        """parents: a parent that is the version itself"""
        lines = self.letter()
        lines[10] = "parent: v2"
        self.planted(lines, counts(3, 2, 1, 1, 1), [(11, "parent is itself")])

    def test_10_parents_a_parent_that_comes_later(self):
        """parents: a parent that comes later"""
        lines = self.letter()
        lines[10] = "parent: v3"
        self.planted(lines, counts(3, 2, 1, 1, 1), [(11, "parent comes later, line 25")])

    def test_10_parents_a_parent_that_does_not_exist(self):
        """parents: a parent that does not exist"""
        lines = self.letter()
        lines[10] = "parent: v9"
        self.planted(lines, counts(3, 2, 1, 1, 1), [(11, "parent not found")])

    def test_10_parents_an_entry_that_names_a_later_version(self):
        """parents: an entry that names a later version"""
        lines = self.letter()
        lines[19] = "version: v3"
        self.planted(lines, counts(3, 3, 1, 1, 1), [(20, "version comes later, line 25")])

    def test_10_parents_an_entry_that_names_a_version_that_does_not_exist(self):
        """parents: an entry that names a version that does not exist"""
        lines = self.letter()
        lines[19] = "version: v9"
        self.planted(lines, counts(3, 3, 1, 1, 1), [(20, "version not found")])

    def test_10_a_version_with_an_empty_change_note(self):
        """a version with an empty change note"""
        lines = self.letter()
        lines[3] = "change: "
        self.planted(lines, counts(3, 3, 1, 1, 1), [(4, "empty change note")])

    def test_10_dates_a_date_that_is_not_a_real_day(self):
        """dates: a date that is not a real day"""
        lines = self.letter()
        lines[2] = "date: 2026-02-30"
        self.planted(lines, counts(3, 3, 1, 1, 1),
                     [(3, "not a date"), (12, "dates cannot be compared, line 1")])

    def test_10_dates_a_version_dated_before_the_result_entry_before_it(self):
        """dates: a version dated before the result entry just before it"""
        lines = self.letter()
        lines[26] = "date: 2026-03-04"
        self.planted(lines, counts(3, 3, 1, 1, 1),
                     [(27, "dated before the section on line 19")])

    def test_10_dates_an_entry_dated_before_the_version_before_it(self):
        """dates: an entry dated before the version just before it"""
        lines = self.letter()
        lines[36] = "date: 2026-03-05"
        self.planted(lines, counts(3, 3, 1, 1, 1),
                     [(37, "dated before the section on line 25")])

    def test_10_two_send_entries(self):
        """two send entries"""
        lines = self.letter() + ["## send", "version: v2", "date: 2026-03-08"]
        self.planted(lines, counts(3, 3, 1, 1, 2), [(38, "a second send entry, first on line 35")])

    def test_10_a_sha256_line_that_does_not_match(self):
        """a `sha256:` line that does not match"""
        lines = self.letter()
        lines[28] = "sha256: " + "0" + V3_SHA[1:]
        self.planted(lines, counts(3, 3, 1, 1, 1), [(29, "sha256 does not match the text")])

    def test_10_an_earlier_copy_that_is_not_the_start_of_the_file(self):
        """an earlier copy that is not the start of the file now"""
        folder = self.work()
        old = text_of("letter-before.txt").replace("Dear Example", "Dear  Example", 1)
        folder.put("older.txt", old)
        code, out, err = self.check("letter.txt", "--earlier", "older.txt")
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail("letter.txt", counts(3, 3, 1, 1, 1), 1,
                                   "earlier copy 260 bytes, file 600 bytes")
                         + "letter.txt:6: differs from the earlier copy\n")

    def test_10_a_file_shorter_than_its_earlier_copy(self):
        """a file shorter than its earlier copy"""
        self.work()
        code, out, err = self.check("letter-before.txt", "--earlier", "letter.txt")
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, fail("letter-before.txt", counts(2, 2, 0, 0, 0), 1,
                                   "earlier copy 600 bytes, file 259 bytes")
                         + "letter-before.txt: shorter than the earlier copy\n")

    def test_10_removing_a_blank_line_is_an_edit_of_earlier_bytes(self):
        """`letter.txt` with its blank line 9 removed gives `letter.txt:9: differs from the
        earlier copy` against `letter-before.txt`, although every version's sha256 is
        unchanged."""
        lines = self.letter()
        self.assertEqual(lines[8], "")
        del lines[8]
        self.assertEqual(digests(joined(lines)), digests(text_of("letter.txt")))
        self.planted(lines, counts(3, 3, 1, 1, 1), [(9, "differs from the earlier copy")],
                     earlier="letter-before.txt")

    def test_10_a_result_entry_whose_run_folder_does_not_exist(self):
        """a result entry whose run folder does not exist: `check` FAILs; `extract` writes the
        version, writes the finding to standard error and exits 0."""
        folder = self.work()
        os.rmdir(folder.path("runs/panel-01"))
        code, out, err = self.check("letter.txt")
        self.assertEqual((code, err, out),
                         (1, "", fail("letter.txt", counts(3, 3, 1, 0, 1), 1)
                          + "letter.txt:22: run folder not found\n"))
        code, out, err = self.extract("letter.txt", "v3", "--out", "v3.txt")
        self.assertEqual((code, out, err),
                         (0, "", "letter.txt:22: run folder not found\n" + NO_EARLIER_LINE))
        with open(folder.path("v3.txt"), "rb") as handle:
            self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), V3_SHA)
        code, out, err = self.extract("letter.txt", "v3", "--out", "v3b.txt", "--earlier",
                                      "letter-before.txt")
        self.assertEqual((code, out, err), (0, "", "letter.txt:22: run folder not found\n"))

    def test_10_every_rule_but_the_run_folder_rule_stops_extract(self):
        """Every rule except the run-folder rule blocks `extract` (section 7)."""
        letter = lines_of(text_of("letter.txt"))

        def edit(changes):
            lines = list(letter)
            for index, text in changes.items():
                lines[index] = text
            return lines
        cases = [
            ("rule 1", edit({15: "## v4"}), None),
            ("rule 2", edit({24: "## v2", 25: "parent: v1", 35: "version: v2"}), None),
            ("rule 3", edit({10: "parent: v9"}), None),
            ("rule 4", edit({3: "change: "}), None),
            ("rule 5", edit({36: "date: 2026-03-05"}), None),
            ("rule 6", letter + ["## send", "version: v2", "date: 2026-03-08"], None),
            ("rule 7", edit({28: "sha256: " + "0" * 64}), None),
            ("rule 8", letter, "older.txt"),
        ]
        for label, lines, earlier in cases:
            with self.subTest(label):
                folder = self.work()
                folder.put("draft.txt", joined(lines))
                folder.put("older.txt", "x" + text_of("letter-before.txt"))
                args = ["draft.txt"] + (["--earlier", earlier] if earlier else [])
                code, out, err = self.check(*args)
                self.assertEqual(code, 1)
                got = self.extract(*(args[:1] + ["v1", "--out", "o.txt"] + args[1:]))
                self.assertEqual(got, (1, "", out))
                self.assertFalse(os.path.lexists(folder.path("o.txt")))


class AndTest(DraftsCase):
    def test_10_a_later_version_that_names_none_is_ok(self):
        """a later version that names `none` is OK"""
        lines = lines_of(text_of("letter.txt"))
        lines[25] = "parent: none"
        folder = self.work()
        folder.put("letter.txt", joined(lines))
        code, out, err = self.check("letter.txt")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "OK    letter.txt: %s; send copy v3; %s\n"
                         % (counts(3, 3, 1, 1, 1), NO_EARLIER))

    def test_10_crlf_and_extra_blank_lines_give_the_same_digest_per_version(self):
        """the same versions with CRLF line breaks, or with more blank lines between sections,
        give the same sha256 for each version"""
        text = text_of("letter.txt")
        want = digests(text)
        self.assertEqual(sorted(want), ["v1", "v2", "v3"])
        self.assertEqual(want["v3"], V3_SHA)
        crlf = text.replace("\n", "\r\n")
        self.assertEqual(digests(crlf), want)
        spaced = text.replace("\n## ", "\n\n\n## ").replace("\n## send", "\n \t\n## send")
        self.assertNotEqual(spaced, text)
        self.assertEqual(digests(spaced), want)
        cr = text.replace("\n", "\r")
        self.assertEqual(digests(cr), want)
        folder = self.work()
        folder.put("crlf.txt", crlf)
        folder.put("spaced.txt", spaced)
        for name in ("crlf.txt", "spaced.txt"):
            with self.subTest(name):
                code, out, err = self.check(name)
                self.assertEqual((code, err), (0, ""))
                self.assertIn("send copy v3", out)

    def test_extract_writes_the_same_bytes_whatever_the_line_breaks(self):
        """`extract` writes exactly the bytes of section 3.2."""
        text = text_of("letter.txt")
        folder = self.work()
        folder.put("crlf.txt", text.replace("\n", "\r\n"))
        folder.put("spaced.txt", text.replace("\n## ", "\n\n\n## "))
        for name in ("crlf.txt", "spaced.txt"):
            with self.subTest(name):
                self.assertEqual(self.extract(name, "v3", "--out", name + ".v3")[0], 0)
                with open(folder.path(name + ".v3"), "rb") as handle:
                    data = handle.read()
                self.assertEqual(hashlib.sha256(data).hexdigest(), V3_SHA)
                self.assertNotIn(b"\r", data)


class SelfTestTest(DraftsCase):
    def test_the_built_in_files_pass(self):
        self.assertIsNone(drafts._self_test())

    def test_each_planted_case_has_its_rule_number_in_order(self):
        self.assertEqual([rule for rule, _call, _expected in drafts._planted()],
                         list(range(1, 10)))

    def test_a_rule_that_finds_nothing_stops_the_run_with_its_number(self):
        for number in range(1, 10):
            for command in (["drafts", "check", "letter.txt"],
                            ["drafts", "extract", "letter.txt", "v1", "--out", "o.txt"]):
                with self.subTest(rule=number, command=command[1]):
                    folder = self.work()
                    name = "rule_%d" % number
                    with unittest.mock.patch.object(drafts, name, lambda *a, **k: []):
                        got = self.cli(command)
                    self.assertEqual(got, (2, "", "cannot run: self-test failed: rule %d\n"
                                           % number))
                    self.assertFalse(os.path.lexists(folder.path("o.txt")))

    def test_a_rule_that_finds_a_fault_that_is_not_planted_stops_the_run(self):
        for number in range(1, 10):
            with self.subTest(rule=number):
                self.work()
                original = getattr(drafts, "rule_%d" % number)

                def noisy(*args, **kwargs):
                    return list(original(*args, **kwargs)) + [(1, "extra")]
                with unittest.mock.patch.object(drafts, "rule_%d" % number, noisy):
                    got = self.check("letter.txt")
                self.assertEqual(got, (2, "", "cannot run: self-test failed: rule %d\n" % number))

    def test_the_self_test_runs_before_the_draft_file_is_read(self):
        with unittest.mock.patch.object(drafts, "rule_6", lambda *a, **k: []):
            got = self.cli(["drafts", "check", "nothing-here.txt"])
        self.assertEqual(got, (2, "", "cannot run: self-test failed: rule 6\n"))

    def test_the_self_test_reads_no_file_and_looks_up_no_path(self):
        real_open = open
        seen = []

        def spy(path, *args, **kwargs):
            seen.append(path)
            return real_open(path, *args, **kwargs)

        def refuse(*args, **kwargs):
            seen.append(args)
            raise AssertionError("looked up a path")
        with unittest.mock.patch("builtins.open", spy), \
                unittest.mock.patch.object(os, "stat", refuse), \
                unittest.mock.patch.object(os, "lstat", refuse), \
                unittest.mock.patch.object(os.path, "isdir", refuse), \
                unittest.mock.patch.object(os.path, "exists", refuse), \
                unittest.mock.patch.object(os.path, "lexists", refuse), \
                unittest.mock.patch.object(os, "listdir", refuse), \
                unittest.mock.patch.object(os, "scandir", refuse):
            self.assertIsNone(drafts._self_test())
        self.assertEqual(seen, [])


class LineTest(DraftsCase):
    def test_split_lines_follows_lf_crlf_and_lone_cr_only(self):
        self.assertEqual(drafts.split_lines("a\nb\r\nc\rd"), ["a", "b", "c", "d"])
        self.assertEqual(drafts.split_lines("a\n"), ["a"])
        self.assertEqual(drafts.split_lines("a\n\n"), ["a", ""])
        self.assertEqual(drafts.split_lines(""), [])
        self.assertEqual(drafts.split_lines("\n"), [""])
        self.assertEqual(drafts.split_lines("a\r\r\nb"), ["a", "", "b"])

    def test_r23_other_separators_neither_end_a_line_nor_make_one_blank(self):
        text = "a" + chr(0x0C) + "b" + chr(0x85) + "c" + chr(0x2028) + "d" + chr(0xA0)
        self.assertEqual(drafts.split_lines(text), [text])
        for char in (chr(0x0C), chr(0x85), chr(0x2028), chr(0xA0)):
            with self.subTest(hex(ord(char))):
                self.assertFalse(drafts.is_blank(char))
                self.assertFalse(drafts.is_blank(" " + char + "\t"))
        self.assertTrue(drafts.is_blank(""))
        self.assertTrue(drafts.is_blank(" \t \t"))

    def test_version_bytes_end_with_exactly_one_line_feed(self):
        draft = drafts.read_draft(drafts.split_lines(
            version("v1", text="one\r\n\r\ntwo  \r\n \t\r\n\r\n")))
        self.assertEqual(drafts.version_bytes(draft.sections[0]), b"one\n\ntwo  \n")


if __name__ == "__main__":
    unittest.main()
