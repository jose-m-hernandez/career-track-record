"""Tests for the re-check before a write into the record folder, and for the files a command
creates anew being opened without following a link. All data here is invented.

The commands that write: ``keywords demand --out``, ``drafts extract --out`` and ``freeze``,
``run`` and ``score`` of ``ab`` and ``panel``. Every case builds its own throwaway git work
tree (git's global and system configuration pointed at the null device), its own config folder
and its own home, so no case reads or writes a real config. Cases that must stop a link being
planted between the check and the open run the command line in this process and patch the one
helper that makes the check."""

import contextlib
import io
import os
import shutil
import sys
import unicodedata
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import cli, drafts, reader_harness, write_guard  # noqa: E402
from tests.test_ab import Setup as AbSetup  # noqa: E402
from tests.test_panel import Setup as PanelSetup  # noqa: E402
from tests.test_record_folder import git, make_repo  # noqa: E402
from tests.test_resolution import (BREAKAGES, CLAIMS_FILE, CLAIMS_LIST, CONTROL, ODD,  # noqa: E402
                                   ODD_SHOWN, Sandbox, message_6)

STOP_TRACKING = "; move the record folder out of git, or stop git tracking the files in it"
HAVE_IGNORED = "; move the record folder out of git, or have git ignore it"
ESCAPES = " is inside the record folder as written but resolves outside it"


class Recheck(Sandbox):
    """A work tree whose ``rec/`` folder is the configured record folder and is ignored."""

    def setUp(self):
        Sandbox.setUp(self)
        self.repo = make_repo(os.path.join(self.tmp, "repo"), ignore="rec/\n")
        self.record = os.path.join(self.repo, "rec")
        os.mkdir(self.record)
        self.put_cfg(self.record)
        self.fixture("drafts/letter.txt", os.path.join(self.tmp, "letter.txt"))
        self.letter = os.path.join(self.tmp, "letter.txt")
        self.postings = self.fixture("keywords/postings-p1", os.path.join(self.tmp, "postings"))
        self.terms = self.fixture("keywords/terms-t1.tsv", os.path.join(self.tmp, "terms.tsv"))
        # A tracked file outside the record folder, and one outside the work tree.
        self.tracked = self.put(os.path.join(self.repo, "tracked.txt"), "tracked, do not touch\n")
        git(self.repo, "add", "tracked.txt")
        git(self.repo, "commit", "-q", "-m", "tracked")
        self.outside = self.put(os.path.join(self.tmp, "outside.txt"), "outside, do not touch\n")

    # -- ways to write -----------------------------------------------------------------

    def extract(self, out, **kw):
        return self.cli("drafts", "extract", self.letter, "v2", "--out", out, **kw)

    def demand(self, out, **kw):
        return self.cli("keywords", "demand", "--postings", self.postings, "--terms", self.terms,
                        "--out", out, **kw)

    def track(self):
        """A file under the record folder becomes tracked (the record folder is now tracked)."""
        slip = self.put(os.path.join(self.record, "slip.txt"), "slipped in\n")
        git(self.repo, "add", "-f", "--", os.path.relpath(slip, self.repo))
        return slip

    def stop_ignoring(self):
        self.put(os.path.join(self.repo, ".gitignore"), "")

    def read(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def refused(self, done, code, line):
        self.assertEqual((done[0], done[1], done[2]), (code, "", line + "\n"))

    def inproc(self, args, patches=(), extra=None):
        """Run the command line in this process: (code, standard output, standard error)."""
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        before = os.getcwd()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, self.env(extra), clear=True))
            stack.enter_context(mock.patch.object(sys, "stdout", out))
            stack.enter_context(mock.patch.object(sys, "stderr", err))
            for patch in patches:
                stack.enter_context(patch)
            os.chdir(self.cwd)
            try:
                code = cli.main(list(args))
            except SystemExit as stop:
                code = stop.code
            finally:
                os.chdir(before)
        return code, out.buffer.getvalue().decode("utf-8"), err.buffer.getvalue().decode("utf-8")


class WritesIntoTheRecordFolder(Recheck):
    def test_s13_a_write_into_an_ignored_folder_goes_ahead_then_a_tracked_file_stops_it(self):
        out = os.path.join(self.record, "out.txt")
        done = self.extract(out)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(os.path.isfile(out))
        self.track()
        second = os.path.join(self.record, "second.txt")
        done = self.extract(second)
        self.refused(done, 1, "refused: %s holds files git tracks; pick a folder git does not "
                              "track%s" % (self.record, STOP_TRACKING))
        self.assertFalse(os.path.exists(second))

    def test_s14_a_folder_git_no_longer_ignores_is_message_10_and_git_missing_is_11(self):
        out = os.path.join(self.record, "out.txt")
        self.stop_ignoring()
        done = self.extract(out)
        self.refused(done, 1, "refused: %s is inside a git work tree and git does not ignore "
                              "it%s" % (self.record, HAVE_IGNORED))
        self.assertFalse(os.path.exists(out))
        done = self.extract(out, path=self.empty_path())
        self.refused(done, 2, "cannot run: cannot tell whether %s is tracked (git was not "
                              "found)" % self.record)
        self.assertFalse(os.path.exists(out))

    def empty_path(self):
        folder = os.path.join(self.tmp, "no-programs")
        os.makedirs(folder, exist_ok=True)
        return folder

    def test_s43_the_refusals_of_a_write_never_tell_the_person_to_choose_again(self):
        out = os.path.join(self.record, "out.txt")
        self.track()
        done = self.extract(out)
        self.assertTrue(done[2].endswith(STOP_TRACKING + "\n"), done)
        self.assertNotIn("choose 1", done[2])
        git(self.repo, "rm", "-q", "--cached", "--", "rec/slip.txt")
        self.stop_ignoring()
        for done in (self.extract(out), self.demand(out)):
            self.assertTrue(done[2].endswith(HAVE_IGNORED + "\n"), done)
            self.assertNotIn("choose 1", done[2])

    def test_every_writing_command_re_checks(self):
        self.track()
        out = os.path.join(self.record, "out.txt")
        want = "refused: %s holds files git tracks; pick a folder git does not track%s\n" % (
            self.record, STOP_TRACKING)
        self.assertEqual(self.demand(out)[1:], ("", want))
        self.assertEqual(self.extract(out)[1:], ("", want))
        self.assertFalse(os.path.exists(out))
        for number, setup in enumerate((AbSetup(self), PanelSetup(self))):
            command = ("ab", "panel")[number]
            folder = os.path.join(self.record, command)
            shutil.copytree(setup.folder, folder)
            plan = os.path.join(folder, "plan.txt")
            for step in ("freeze", "run", "score"):
                with self.subTest(command=command, step=step):
                    self.assertEqual(self.cli(command, step, plan)[1:], ("", want))
            self.assertFalse(os.path.exists(plan + ".freeze"))

    def test_the_command_s_own_answer_stays_when_the_re_check_passes(self):
        out = os.path.join(self.record, "demand.txt")
        done = self.demand(out)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(self.read(out).startswith(b"# Demand,"))
        self.assertEqual(done[2], "")

    def test_a_refused_write_writes_nothing_on_standard_output_or_anywhere(self):
        self.track()
        before = sorted(os.listdir(self.record))
        done = self.demand(os.path.join(self.record, "out.txt"))
        self.assertEqual((done[0], done[1]), (1, ""))
        self.assertEqual(sorted(os.listdir(self.record)), before)


class AnUnusableConfigStopsTheWrite(Recheck):
    def test_s15a_each_breakage_stops_every_writing_command_and_changes_no_reader(self):
        ab, panel = AbSetup(self), PanelSetup(self)
        outside = os.path.join(self.tmp, "outputs")
        os.mkdir(outside)
        self.put(os.path.join(self.tmp, "mine.tsv"), CLAIMS_LIST)
        self.put(os.path.join(self.tmp, "f.txt"), CLAIMS_FILE)
        self.fixture("barred/list-l1.txt", os.path.join(self.tmp, "list-l1.txt"))
        self.fixture("barred/clean.txt", os.path.join(self.tmp, "clean.txt"))
        self.fixture("tone/rules-r1.json", os.path.join(self.tmp, "rules.json"))
        self.fixture("tone/case-11-01.txt", os.path.join(self.tmp, "case.txt"))
        self.fixture("keywords/copy.txt", os.path.join(self.tmp, "copy.txt"))
        readers = (
            ("claims", "--list", "mine.tsv", "--control", CONTROL, "f.txt"),
            ("barred", "--list", "list-l1.txt", "--control", "Example Corp", "clean.txt"),
            ("tone", "--rules", "rules.json", "case.txt"),
            ("keywords", "report", "--postings", self.postings, "--terms", self.terms,
             "--copy", "copy.txt"),
            ("drafts", "check", self.letter))
        os.remove(self.cfg)
        plain = [self.cli(*args, cwd=self.tmp) for args in readers]
        for name, raw, reason in BREAKAGES:
            with self.subTest(breakage=name):
                self.put_cfg(raw=raw)
                writes = (
                    ("drafts", "extract", self.letter, "v2", "--out",
                     os.path.join(outside, "x.txt")),
                    ("keywords", "demand", "--postings", self.postings, "--terms", self.terms,
                     "--out", os.path.join(outside, "y.txt")),
                    ("ab", "freeze", ab.plan_path), ("panel", "freeze", panel.plan_path))
                for args in writes:
                    self.assertEqual(self.cli(*args), (2, "", message_6(reason)), args)
                self.assertEqual(os.listdir(outside), [])
                self.assertFalse(os.path.exists(ab.plan_path + ".freeze"))
                self.assertFalse(os.path.exists(panel.plan_path + ".freeze"))
                self.assertEqual([self.cli(*args, cwd=self.tmp) for args in readers], plain)

    def test_s15a_a_record_folder_that_is_missing_does_not_stop_a_write_given_all_paths(self):
        self.put_cfg(os.path.join(self.tmp, "gone"))
        out = os.path.join(self.tmp, "o.txt")
        self.assertEqual(self.extract(out)[0], 0)

    def test_s15b_no_config_file_means_no_re_check_even_in_a_tracked_checkout(self):
        self.track()
        os.remove(self.cfg)
        out = os.path.join(self.record, "out.txt")
        done = self.extract(out)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(os.path.isfile(out))
        done = self.demand(os.path.join(self.record, "demand.txt"))
        self.assertEqual(done[0], 0, done)

    def test_s15b_no_config_file_ab_freeze_runs_as_before(self):
        self.track()
        os.remove(self.cfg)
        setup = AbSetup(self)
        folder = os.path.join(self.record, "p")
        shutil.copytree(setup.folder, folder)
        done = self.cli("ab", "freeze", os.path.join(folder, "plan.txt"))
        self.assertEqual(done, (0, "freeze written: plan.txt.freeze\n", ""))


class ContainmentIsDecidedByTheFileSystem(Recheck):
    def test_s16_a_configured_link_to_the_folder_and_the_folder_itself_both_re_check(self):
        link = os.path.join(self.tmp, "link-to-record")
        os.symlink(self.record, link)
        self.put_cfg(link)
        self.track()
        for name, folder in (("through the link", link), ("directly", self.record)):
            with self.subTest(name):
                out = os.path.join(folder, "out-%s.txt" % name.split()[0])
                done = self.extract(out)
                self.refused(done, 1, "refused: %s holds files git tracks; pick a folder git "
                                      "does not track%s" % (link, STOP_TRACKING))
                self.assertFalse(os.path.exists(out))

    def test_s16_a_configured_link_lets_a_write_through_while_the_folder_is_ignored(self):
        link = os.path.join(self.tmp, "link-to-record")
        os.symlink(self.record, link)
        self.put_cfg(link)
        for folder in (link, self.record):
            out = os.path.join(folder, "ok-%d.txt" % len(os.listdir(self.record)))
            self.assertEqual(self.extract(out)[0], 0)
            self.assertTrue(os.path.isfile(out))

    def test_s16_a_sibling_outside_the_record_folder_is_not_re_checked(self):
        self.track()
        sibling = os.path.join(self.repo, "other")
        os.mkdir(sibling)
        out = os.path.join(sibling, "out.txt")
        done = self.extract(out)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(os.path.isfile(out))

    def test_s16a_a_leaf_link_out_of_the_folder_is_message_12_and_the_target_is_untouched(self):
        report = os.path.join(self.record, "report.txt")
        os.symlink(self.tracked, report)
        before = self.read(self.tracked)
        done = self.demand(report)
        self.refused(done, 1, "refused: %s%s" % (report, ESCAPES))
        self.assertEqual(self.read(self.tracked), before)
        os.remove(report)
        done = self.demand(report)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(os.path.isfile(report) and not os.path.islink(report))

    def test_s16a_the_same_for_drafts_extract(self):
        report = os.path.join(self.record, "report.txt")
        os.symlink(self.outside, report)
        done = self.extract(report)
        self.refused(done, 1, "refused: %s%s" % (report, ESCAPES))
        self.assertEqual(self.read(self.outside), b"outside, do not touch\n")

    def test_s16a_a_dangling_link_out_of_the_folder_is_refused_too(self):
        report = os.path.join(self.record, "dangling.txt")
        os.symlink(os.path.join(self.tmp, "not-there.txt"), report)
        done = self.extract(report)
        self.refused(done, 1, "refused: %s%s" % (report, ESCAPES))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "not-there.txt")))

    def test_s16b_a_folder_link_out_of_the_folder_for_drafts_extract_and_ab_freeze(self):
        away = os.path.join(self.tmp, "away")
        os.mkdir(away)
        os.symlink(away, os.path.join(self.record, "plans"))
        target = os.path.join(self.record, "plans", "out.txt")
        done = self.extract(target)
        self.refused(done, 1, "refused: %s%s" % (target, ESCAPES))
        self.assertEqual(os.listdir(away), [])
        setup = AbSetup(self)
        for name in os.listdir(setup.folder):
            shutil.copyfile(os.path.join(setup.folder, name), os.path.join(away, name))
        plan = os.path.join(self.record, "plans", "plan.txt")
        done = self.cli("ab", "freeze", plan)
        self.refused(done, 1, "refused: %s.freeze%s" % (plan, ESCAPES))
        self.assertFalse(os.path.exists(os.path.join(away, "plan.txt.freeze")))

    def test_s16c_a_name_outside_that_is_a_link_to_a_file_inside_re_checks_the_folder(self):
        alias = os.path.join(self.repo, "alias.txt")
        os.symlink(os.path.join(self.record, "new.txt"), alias)
        self.track()
        done = self.extract(alias)
        self.refused(done, 1, "refused: %s holds files git tracks; pick a folder git does not "
                              "track%s" % (self.record, STOP_TRACKING))
        self.assertFalse(os.path.exists(os.path.join(self.record, "new.txt")))

    def test_s16c_the_same_link_with_the_folder_ignored_writes_through_it(self):
        alias = os.path.join(self.repo, "alias.txt")
        os.symlink(os.path.join(self.record, "new.txt"), alias)
        done = self.demand(alias)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(os.path.isfile(os.path.join(self.record, "new.txt")))

    def test_s16d_a_link_planted_after_the_check_is_not_followed(self):
        new = os.path.join(self.record, "new.txt")
        real = cli.write_guard.recheck

        def check_then_plant(targets, environ=None):
            answer = real(targets, environ)
            if list(targets) == [new]:
                os.symlink(self.outside, new)
            return answer

        done = self.inproc(("keywords", "demand", "--postings", self.postings, "--terms",
                            self.terms, "--out", new),
                           [mock.patch.object(cli.write_guard, "recheck", check_then_plant)])
        self.assertEqual(done[0], 2, done)
        self.assertEqual(done[1], "")
        self.assertRegex(done[2], r"^cannot run: cannot write %s: .+\n\Z" % new)
        self.assertEqual(done[2].count("\n"), 1)
        self.assertEqual(self.read(self.outside), b"outside, do not touch\n")
        self.assertTrue(os.path.islink(new))

    def test_s16d_a_link_planted_after_the_newness_decision_is_refused_by_the_check(self):
        new = os.path.join(self.record, "new.txt")
        real = cli._target_is_new

        def decide_then_plant(path):
            answer = real(path)
            if path == new and answer:
                os.symlink(self.outside, new)
            return answer

        done = self.inproc(("keywords", "demand", "--postings", self.postings, "--terms",
                            self.terms, "--out", new),
                           [mock.patch.object(cli, "_target_is_new", decide_then_plant)])
        self.refused(done, 1, "refused: %s%s" % (new, ESCAPES))
        self.assertEqual(self.read(self.outside), b"outside, do not touch\n")
        self.assertTrue(os.path.islink(new))

    def test_s16d_a_regular_file_that_exists_is_truncated_and_written_as_before(self):
        existing = self.put(os.path.join(self.record, "old.txt"), "old text that is long\n" * 50)
        done = self.demand(existing)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(self.read(existing).startswith(b"# Demand,"))
        self.assertNotIn(b"old text", self.read(existing))

    def test_s16d_the_out_file_is_made_with_a_no_follow_open(self):
        seen = []
        real = os.open

        def spy(path, flags, *rest, **kw):
            seen.append((path, flags))
            return real(path, flags, *rest, **kw)

        new = os.path.join(self.record, "flags.txt")
        done = self.inproc(("keywords", "demand", "--postings", self.postings, "--terms",
                            self.terms, "--out", new), [mock.patch("os.open", spy)])
        self.assertEqual(done[0], 0, done)
        flags = [f for p, f in seen if p == new]
        self.assertEqual(len(flags), 1)
        wanted = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        self.assertEqual(flags[0] & wanted, wanted)

    def test_s16d_the_extracted_file_is_made_with_a_no_follow_open(self):
        seen = []
        real = os.open

        def spy(path, flags, *rest, **kw):
            seen.append((path, flags))
            return real(path, flags, *rest, **kw)

        new = os.path.join(self.record, "flags.txt")
        done = self.inproc(("drafts", "extract", self.letter, "v2", "--out", new),
                           [mock.patch("os.open", spy)])
        self.assertEqual(done[0], 0, done)
        flags = [f for p, f in seen if p == new]
        self.assertEqual(len(flags), 1)
        wanted = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        self.assertEqual(flags[0] & wanted, wanted)

    def test_s16e_a_hostile_name_in_message_12_is_one_escaped_line(self):
        link = os.path.join(self.record, ODD)
        os.symlink(self.tracked, link)
        done = self.demand(link)
        self.assertEqual(done[0:2], (1, ""))
        self.assertEqual(done[2], "refused: %s/rec/%s%s\n" % (self.repo, ODD_SHOWN, ESCAPES))
        self.assertEqual(done[2].count("\n"), 1)

    def test_s16e_a_hostile_name_in_the_cannot_write_line(self):
        parent = os.path.join(self.tmp, "ro")
        os.mkdir(parent)
        os.chmod(parent, 0o500)
        self.addCleanup(os.chmod, parent, 0o700)
        if os.access(parent, os.W_OK):
            self.skipTest("this account can write to a read-only folder")
        done = self.demand(os.path.join(parent, ODD))
        self.assertEqual(done[0:2], (2, ""))
        self.assertTrue(done[2].startswith("cannot run: cannot write %s/%s: " % (parent,
                                                                                   ODD_SHOWN)))
        self.assertEqual(done[2].count("\n"), 1)

    def test_s16g_a_link_planted_at_the_freeze_file_is_not_followed(self):
        setup = AbSetup(self)
        folder = os.path.join(self.record, "plan")
        shutil.copytree(setup.folder, folder)
        plan = os.path.join(folder, "plan.txt")
        freeze = plan + ".freeze"
        real = reader_harness.freeze_files

        def check_then_plant(path):
            names = real(path)
            if not os.path.lexists(freeze):
                os.symlink(self.outside, freeze)
            return names

        done = self.inproc(("ab", "freeze", plan),
                           [mock.patch.object(reader_harness, "freeze_files", check_then_plant)])
        self.assertEqual(done, (2, "", "cannot run: cannot write plan.txt.freeze: File exists\n"))
        self.assertEqual(self.read(self.outside), b"outside, do not touch\n")
        os.remove(freeze)
        done = self.cli("ab", "freeze", plan)
        self.assertEqual(done, (0, "freeze written: plan.txt.freeze\n", ""))

    def test_s16g_a_link_planted_at_the_extracted_file_is_not_followed(self):
        new = os.path.join(self.record, "new.txt")
        real = drafts._exists

        def check_then_plant(path):
            answer = real(path)
            if path == new and not answer:
                os.symlink(self.outside, new)
            return answer

        done = self.inproc(("drafts", "extract", self.letter, "v2", "--out", new),
                           [mock.patch.object(drafts, "_exists", check_then_plant)])
        self.assertEqual(done[0], 2, done)
        self.assertEqual(done[1], "")
        self.assertTrue(done[2].endswith("cannot run: cannot write output\n"), done)
        self.assertEqual(self.read(self.outside), b"outside, do not touch\n")
        os.remove(new)
        self.assertEqual(self.extract(new)[0], 0)

    def test_s16g_every_new_file_of_a_run_is_opened_with_a_no_follow_flag(self):
        for number, setup in enumerate((AbSetup(self), PanelSetup(self))):
            command = ("ab", "panel")[number]
            folder = os.path.join(self.record, command)
            shutil.copytree(setup.folder, folder)
            plan = os.path.join(folder, "plan.txt")
            self.assertEqual(self.cli(command, "freeze", plan)[0], 0)
            seen = []
            real = os.open

            def spy(path, flags, *rest, **kw):
                seen.append((path, flags))
                return real(path, flags, *rest, **kw)

            with self.subTest(command=command):
                done = self.inproc((command, "run", plan), [mock.patch("os.open", spy)])
                self.assertEqual(done[0], 0, done)
                made = [(p, f) for p, f in seen if str(p).startswith(folder)]
                self.assertGreater(len(made), 10)
                wanted = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                for path, flags in made:
                    self.assertEqual(flags & wanted, wanted, path)


class EveryWriteOfAbAndPanel(Recheck):
    """A link planted at each path ``freeze``, ``run`` and ``score`` create (see the inventory
    of writes in write_guard.plan_targets)."""

    def folder_for(self, which):
        setup = (AbSetup, PanelSetup)[which](self)
        folder = os.path.join(self.record, "run")
        shutil.copytree(setup.folder, folder)
        return ("ab", "panel")[which], folder, os.path.join(folder, "plan.txt")

    def planted(self, name):
        away = os.path.join(self.tmp, "away-" + name)
        self.put(away, "away, do not touch\n")
        return away

    def test_a_link_at_the_freeze_file(self):
        for which in (0, 1):
            command, folder, plan = self.folder_for(which)
            away = self.planted("freeze%d" % which)
            os.symlink(away, plan + ".freeze")
            with self.subTest(command=command):
                done = self.cli(command, "freeze", plan)
                self.refused(done, 1, "refused: %s.freeze%s" % (plan, ESCAPES))
                self.assertEqual(self.read(away), b"away, do not touch\n")
            shutil.rmtree(folder)

    def test_a_link_at_key_run_log_and_reads_for_run(self):
        for which in (0, 1):
            for name in ("key.txt", "run-log.txt", "reads"):
                command, folder, plan = self.folder_for(which)
                self.assertEqual(self.cli(command, "freeze", plan)[0], 0)
                away = self.planted("%s%d" % (name.replace(".", ""), which))
                if name == "reads":
                    os.remove(away)
                    os.mkdir(away)
                os.symlink(away, os.path.join(folder, name))
                with self.subTest(command=command, name=name):
                    done = self.cli(command, "run", plan)
                    self.refused(done, 1, "refused: %s/%s%s" % (folder, name, ESCAPES))
                    if name != "reads":
                        self.assertEqual(self.read(away), b"away, do not touch\n")
                    else:
                        self.assertEqual(os.listdir(away), [])
                shutil.rmtree(folder)

    def test_a_link_at_the_next_result_file_is_skipped_by_run_and_score(self):
        for which in (0, 1):
            command, folder, plan = self.folder_for(which)
            self.assertEqual(self.cli(command, "freeze", plan)[0], 0)
            away = self.planted("result%d" % which)
            os.symlink(away, os.path.join(folder, "result-1.txt"))
            with self.subTest(command=command):
                done = self.cli(command, "run", plan)
                self.assertEqual(done[0], 0, done)
                self.assertEqual(self.read(away), b"away, do not touch\n")
                self.assertTrue(os.path.isfile(os.path.join(folder, "result-2.txt")))
                os.symlink(away, os.path.join(folder, "result-3.txt"))
                done = self.cli(command, "score", plan)
                self.assertEqual(done[0], 0, done)
                self.assertEqual(self.read(away), b"away, do not touch\n")
                self.assertTrue(os.path.isfile(os.path.join(folder, "result-4.txt")))
            shutil.rmtree(folder)

    def test_a_link_at_the_plan_s_folder_for_each_command(self):
        for which in (0, 1):
            setup = (AbSetup, PanelSetup)[which](self)
            command = ("ab", "panel")[which]
            link = os.path.join(self.record, "via-%s" % command)
            os.symlink(setup.folder, link)
            plan = os.path.join(link, "plan.txt")
            for step in ("freeze", "run", "score"):
                with self.subTest(command=command, step=step):
                    done = self.cli(command, step, plan)
                    self.assertEqual(done[0:2], (1, ""), done)
                    self.assertTrue(done[2].endswith(ESCAPES + "\n"), done)
            self.assertEqual(sorted(n for n in os.listdir(setup.folder)
                                    if n.endswith(".freeze") or n in ("reads", "key.txt")), [])

    def test_the_targets_are_the_files_a_command_makes_and_the_folder(self):
        folder = os.path.join(self.tmp, "p")
        plan = os.path.join(folder, "plan.txt")
        self.assertEqual(write_guard.plan_targets("freeze", plan),
                         [plan + ".freeze", folder])
        self.assertEqual(write_guard.plan_targets("run", plan),
                         [folder + "/key.txt", folder + "/run-log.txt", folder + "/reads",
                          folder + "/result-1.txt", folder])
        self.assertEqual(write_guard.plan_targets("score", plan),
                         [folder + "/result-1.txt", folder])
        os.makedirs(folder)
        self.put(folder + "/result-1.txt", "x")
        os.symlink(self.outside, folder + "/result-2.txt")
        self.assertEqual(write_guard.plan_targets("score", plan)[0], folder + "/result-3.txt")


class WhereCaseAndNormalisationDiffer(Recheck):
    """The record folder is spelled with a composed e-acute; the other spellings name the same
    folder only on a volume that folds case and normalisation."""

    def setUp(self):
        Recheck.setUp(self)
        self.record = os.path.join(self.repo, "récord")
        os.mkdir(self.record)
        self.put(os.path.join(self.repo, ".gitignore"), "récord/\n")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        self.put_cfg(self.record)

    def spelling(self, name):
        """The record folder spelled ``upper`` or ``nfd``; skips unless the volume agrees."""
        if name == "upper":
            other = os.path.join(self.repo, "RÉCORD")
        else:
            other = os.path.join(self.repo, unicodedata.normalize("NFD", "récord"))
        if not os.path.exists(other) or not os.path.samefile(other, self.record):
            self.skipTest("skipped: volume does not fold case")
        return other

    def test_s16f_the_control_spelled_as_in_the_config(self):
        report = os.path.join(self.record, "report.txt")
        os.symlink(self.tracked, report)
        done = self.demand(report)
        self.refused(done, 1, "refused: %s%s" % (report, ESCAPES))
        self.assertEqual(self.read(self.tracked), b"tracked, do not touch\n")
        os.remove(report)
        self.track()
        new = os.path.join(self.record, "new.txt")
        done = self.demand(new)
        self.refused(done, 1, "refused: %s holds files git tracks; pick a folder git does not "
                              "track%s" % (self.record, STOP_TRACKING))

    def test_s16f_a_leaf_link_through_an_upper_case_or_decomposed_spelling(self):
        os.symlink(self.tracked, os.path.join(self.record, "report.txt"))
        for name in ("upper", "nfd"):
            with self.subTest(spelling=name):
                other = self.spelling(name)
                target = os.path.join(other, "report.txt")
                done = self.demand(target)
                self.refused(done, 1, "refused: %s%s" % (target, ESCAPES))
                self.assertEqual(self.read(self.tracked), b"tracked, do not touch\n")

    def test_s16f_a_tracked_folder_through_an_upper_case_or_decomposed_spelling(self):
        self.track()
        for name in ("upper", "nfd"):
            with self.subTest(spelling=name):
                other = self.spelling(name)
                target = os.path.join(other, "new-%s.txt" % name)
                done = self.demand(target)
                self.refused(done, 1, "refused: %s holds files git tracks; pick a folder git "
                                      "does not track%s" % (self.record, STOP_TRACKING))
                self.assertFalse(os.path.exists(target))


class ReadsAreNotRechecked(Recheck):
    def test_s17_readers_read_files_under_a_tracked_record_folder_as_without_a_config(self):
        self.track()
        self.put(os.path.join(self.record, "mine.tsv"), CLAIMS_LIST)
        self.put(os.path.join(self.record, "f.txt"), CLAIMS_FILE)
        self.fixture("barred/list-l1.txt", os.path.join(self.record, "list-l1.txt"))
        self.fixture("barred/clean.txt", os.path.join(self.record, "clean.txt"))
        self.fixture("tone/rules-r1.json", os.path.join(self.record, "rules.json"))
        self.fixture("tone/case-11-01.txt", os.path.join(self.record, "case.txt"))
        self.fixture("keywords/copy.txt", os.path.join(self.record, "copy.txt"))
        self.fixture("drafts/letter.txt", os.path.join(self.record, "letter.txt"))
        commands = (
            ("claims", "--list", "mine.tsv", "--control", CONTROL, "f.txt"),
            ("barred", "--list", "list-l1.txt", "--control", "Example Corp", "clean.txt"),
            ("tone", "--rules", "rules.json", "case.txt"),
            ("keywords", "report", "--postings", self.postings, "--terms", self.terms,
             "--copy", "copy.txt"),
            ("drafts", "check", "letter.txt"))
        with_config = [self.cli(*args, cwd=self.record) for args in commands]
        os.remove(self.cfg)
        without = [self.cli(*args, cwd=self.record) for args in commands]
        self.assertEqual(with_config, without)
        for done in with_config:
            self.assertNotIn("refused", done[2])

    def test_s17_a_write_outside_the_folder_is_not_re_checked_in_a_tracked_checkout(self):
        self.track()
        out = os.path.join(self.tmp, "elsewhere.txt")
        done = self.demand(out)
        self.assertEqual(done[0], 0, done)
        self.assertTrue(os.path.isfile(out))


class InsideIsAskedOfTheFileSystem(unittest.TestCase):
    """The helper that decides containment, on its own."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.root = os.path.join(self.tmp, "root")
        os.makedirs(os.path.join(self.root, "sub"))

    def test_the_folder_itself_a_child_a_missing_child_and_a_stranger(self):
        self.assertTrue(write_guard.inside(self.root, self.root))
        self.assertTrue(write_guard.inside(os.path.join(self.root, "sub"), self.root))
        self.assertTrue(write_guard.inside(os.path.join(self.root, "sub", "no", "x.txt"),
                                           self.root))
        self.assertFalse(write_guard.inside(os.path.join(self.tmp, "other", "x.txt"), self.root))
        self.assertFalse(write_guard.inside(self.tmp, self.root))

    def test_a_string_prefix_is_not_containment(self):
        sibling = self.root + "-sibling"
        os.mkdir(sibling)
        self.assertFalse(write_guard.inside(os.path.join(sibling, "x.txt"), self.root))

    def test_a_link_to_the_folder_is_the_folder(self):
        link = os.path.join(self.tmp, "link")
        os.symlink(self.root, link)
        self.assertTrue(write_guard.inside(os.path.join(link, "x.txt"), self.root))
        self.assertTrue(write_guard.inside(os.path.join(self.root, "x.txt"), link))


if __name__ == "__main__":
    unittest.main()
