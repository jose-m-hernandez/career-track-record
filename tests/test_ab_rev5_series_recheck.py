"""Tests for the series write of ``ab run`` and ``ab score`` being checked against the record
folder (cases A1 to A10 of the setup spec's section 7.5 addendum). All data here is invented.

The series file ``S`` is written by hand, lies in a folder the plan names, and ``ab run`` and
``ab score`` replace it. Three paths are written: ``S``, ``S.lock`` and a temporary file in the
folder of ``S``. Every case builds the throwaway work tree of ``tests/test_write_recheck.py``:
its ``rec/`` folder is the configured record folder ``R`` and is ignored, and git's global and
system configuration point at the null device. Each plan names its own series file by an
absolute path, so that one case can hold several rounds without a draft being written twice.

The series spec's third check wants the plan's folder strictly below the folder of ``S``, so a
plan whose series file is inside ``R`` is inside ``R`` too, and the only plan that is outside
``R`` while ``S`` is inside it is one that check would refuse anyway. The re-check comes first,
so such a plan is still refused by the re-check, and ``ab`` is given one by building a valid
round and then moving its folder (plan, freeze file and results) out of ``R`` (``move_out``);
the plan's text, and so its hash, does not change.

The command line is run in this process (``Recheck.inproc``), which is the surface the person
uses. The cases that need the order of the checks, or the plan's own targets, call ``ab``
directly with this process's environment set to the sandbox's, because the command line
re-checks the plan's own targets before ``ab`` runs and would hide the call that is tested.

Where a case says what a wrong rule would give, the comment beside the assertion names that
wrong answer: it is the mutant the assertion must turn red.

Each case id has one test method named test_aN_...; a case that needed more than one method
has the others as test_aNb_..., test_aNc_... .
"""

import io
import os
import shutil
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import ab, cli, series, write_guard  # noqa: E402
from career_track_record.barred import printed_path  # noqa: E402
from tests.test_ab_rev5_series import BASE_ROW, CLOCK, HEADER, Round  # noqa: E402
from tests.test_record_folder import git  # noqa: E402
from tests.test_resolution import BREAKAGES, message_6  # noqa: E402
from tests.test_write_recheck import HAVE_IGNORED, STOP_TRACKING, Recheck  # noqa: E402

ESCAPES = " is inside the record folder as written but resolves outside it"
TAIL = "; the result is kept; fix this, then re-run ab score on the plan to add the row"


class SeriesRecheck(Recheck):
    """``R`` is ``rec/`` of the work tree; rounds are made inside or outside it."""

    # -- rounds and files --------------------------------------------------------------

    def make(self, name, series_dir=None, plan_dir=None, **overrides):
        """A round ``name`` in ``series_dir`` (default ``R``) whose plan names its own series
        file ``<series_dir>/s-<name>.series.tsv`` by its absolute path, written by hand with its
        header and the row ``base``. The plan's folder is ``<plan_dir>/<name>`` (default: the folder of
        the series file, so below it)."""
        folder = series_dir or self.record
        where = os.path.join(folder, "s-%s.series.tsv" % name)
        self.put(where, HEADER + "\n" + BASE_ROW + "\n")
        values = dict(series=where)
        values.update(overrides)
        r = Round(self, plan_dir or folder, name, **values)
        r.series_file, r.shown = where, where
        return r

    def move_out(self, r):
        """The round's folder, with its freeze file and results, moved out of ``R``: the plan
        is now outside the record folder and its text is as it was."""
        root = os.path.join(self.tmp, "plans")
        os.makedirs(root, exist_ok=True)
        folder = os.path.join(root, os.path.basename(r.folder))
        shutil.move(r.folder, folder)
        r.folder, r.plan_path = folder, os.path.join(folder, "plan.txt")
        return r

    def bytes_of(self, r):
        return self.read(r.series_file)

    def suffix(self, r):
        return " (series file %s)" % printed_path(r.shown)

    def call(self, r, step, extra=None, patches=()):
        """The command line, in this process: (code, standard output, standard error)."""
        return self.inproc(("ab", step, r.plan_path), patches, extra)

    def ok(self, r, step):
        done = self.call(r, step)
        self.assertEqual((done[0], done[2]), (0, ""), done)
        return done

    def direct(self, call, *args, **kwargs):
        """``ab.freeze``, ``ab.run`` or ``ab.score`` called directly, with this process's
        environment set to the sandbox's and the clock of the series cases."""
        with mock.patch.dict(os.environ, self.env(), clear=True):
            return call(*args, now=CLOCK, **kwargs)

    # -- the refusal lines as ``write_guard`` prints them ------------------------------

    def line9(self):
        return ("refused: %s holds files git tracks; pick a folder git does not track%s"
                % (self.record, STOP_TRACKING))

    def line10(self):
        return ("refused: %s is inside a git work tree and git does not ignore it%s"
                % (self.record, HAVE_IGNORED))

    def line11(self):
        return "cannot run: cannot tell whether %s is tracked (git was not found)" % self.record

    def empty_path(self):
        folder = os.path.join(self.tmp, "no-programs")
        os.makedirs(folder, exist_ok=True)
        return folder

    def untrack(self):
        if git(self.repo, "ls-files", "--", "rec/slip.txt").strip():
            git(self.repo, "rm", "-q", "--cached", "--", "rec/slip.txt")

    # -- the three steps, spoiled between the checks that passed and the refusal -------

    def steps(self, inside, spoil, extra=None):
        """A bare round for freeze, a frozen round for run and a run round for score, each with
        its own series file, each moved out of ``R`` unless ``inside``; then ``spoil()``; then each
        step on the command line, with ``extra`` in its environment. Returns [(step, round, done,
        series bytes before the step)]."""
        bare = self.make("f")
        frozen = self.make("u")
        self.ok(frozen, "freeze")
        ran = self.make("s")
        self.ok(ran, "freeze")
        self.ok(ran, "run")
        if not inside:
            for r in (bare, frozen, ran):
                self.move_out(r)
        spoil()
        got = []
        for step, r in (("freeze", bare), ("run", frozen), ("score", ran)):
            before = self.bytes_of(r)
            got.append((step, r, self.call(r, step, extra), before))
        return got

    def assert_refused(self, got, code, line, suffix):
        """Every step refused with ``code`` and ``line`` (plus the series-file suffix when
        ``suffix``), on standard error once, and wrote nothing: the series file is
        byte-identical, no freeze file, no reads folder, no new result."""
        for step, r, done, before in got:
            with self.subTest(step=step, inside=not suffix):
                want = line + (self.suffix(r) if suffix else "")
                self.assertEqual(done, (code, "", want + "\n"))
                self.assertEqual(self.bytes_of(r), before)
                if step == "freeze":
                    self.assertFalse(r.exists("plan.txt.freeze"))
                elif step == "run":
                    # before any read: no reads folder, no result
                    self.assertFalse(r.exists(ab.READS_DIR))
                    self.assertFalse(r.exists("result-1.txt"))
                else:
                    self.assertTrue(r.exists("result-1.txt"))
                    self.assertFalse(r.exists("result-2.txt"))


class AdmittedWrites(SeriesRecheck):
    def test_a1_a_series_file_in_a_clean_ignored_record_folder_is_written(self):
        r = self.make("a1")
        self.ok(r, "freeze")
        done = self.call(r, "run")
        self.assertEqual((done[0], done[2]), (0, ""), done)
        self.assertEqual(done[1].splitlines()[-1], "series: added row skills-top to %s" % r.shown)
        self.assertEqual(len(self.bytes_of(r).split(b"\n")), 4)

    def test_a10_no_config_file_means_no_re_check_on_any_of_the_three_paths(self):
        os.remove(self.cfg)
        self.track()
        self.stop_ignoring()
        r = self.make("a10")
        self.ok(r, "freeze")
        done = self.call(r, "run")
        self.assertEqual((done[0], done[2]), (0, ""), done)
        self.assertEqual(done[1].splitlines()[-1], "series: added row skills-top to %s" % r.shown)
        self.assertEqual(len(self.bytes_of(r).split(b"\n")), 4)


class RefusedBeforeTheResult(SeriesRecheck):
    def test_a2_a_tracked_record_folder_refuses_the_series_file_and_names_it(self):
        got = self.steps(False, self.track)
        # a mutant that does not re-check the series paths lets all three go through
        self.assert_refused(got, 1, self.line9(), suffix=True)

    def test_a2b_the_plans_own_targets_are_checked_first_and_take_no_suffix(self):
        self.track()
        inside = self.make("in")
        outside = self.move_out(self.make("out"))
        before = (self.bytes_of(inside), self.bytes_of(outside))
        # direct calls, so that the command line's own check does not stand in for the call
        # that is tested. A mutant that skips the plan's own targets and checks the series
        # paths only prints the suffix on the first of these lines.
        done = self.direct(ab.freeze, inside.plan_path)
        self.assertEqual((done.exit_code, done.ran, done.error), (1, False, self.line9()))
        done = self.direct(ab.freeze, outside.plan_path)
        self.assertEqual((done.exit_code, done.ran, done.error),
                         (1, False, self.line9() + self.suffix(outside)))
        self.assertEqual((self.bytes_of(inside), self.bytes_of(outside)), before)
        for r in (inside, outside):
            self.assertFalse(r.exists("plan.txt.freeze"))
            self.assertFalse(r.exists("result-1.txt"))

    def test_a2c_on_the_command_line_a_plan_inside_the_folder_gets_the_plans_own_refusal(self):
        self.track()
        r = self.make("in")
        before = self.bytes_of(r)
        done = self.call(r, "freeze")
        self.assertEqual(done, (1, "", self.line9() + "\n"))
        self.assertNotIn("series file", done[2])
        self.assertEqual(self.bytes_of(r), before)

    def test_a3_a_folder_git_does_not_ignore_is_message_10_and_names_the_series_file(self):
        got = self.steps(False, self.stop_ignoring)
        self.assert_refused(got, 1, self.line10(), suffix=True)

    def test_a3b_with_the_plan_inside_the_folder_the_line_has_no_suffix(self):
        got = self.steps(True, self.stop_ignoring)
        self.assert_refused(got, 1, self.line10(), suffix=False)

    def test_a4_git_that_cannot_run_is_message_11_exit_2_at_freeze_run_and_score(self):
        empty = {"PATH": self.empty_path()}
        got = self.steps(False, lambda: None, extra=empty)
        # exit 2 for each: setup gives message 11 exit 2 before the result exists
        self.assert_refused(got, 2, self.line11(), suffix=True)
        self.assertEqual([done[0] for _step, _r, done, _before in got], [2, 2, 2])

    def test_a5_the_plan_outside_and_the_series_file_inside_is_checked_on_the_series_file(self):
        self.track()
        r = self.move_out(self.make("a5"))
        done = self.call(r, "freeze")
        # the plan's folder is outside R and passes; the series file's folder is inside it
        self.assertEqual(done, (1, "", self.line9() + self.suffix(r) + "\n"))

    def test_a5b_the_plan_inside_and_the_series_file_outside_checks_the_plans_writes_only(self):
        # R is clean and ignored, so the plan's own writes are allowed; the series file lies in
        # the work tree, above R, tracked, and is not re-checked.
        r = self.make("a5b", series_dir=self.repo, plan_dir=self.record)
        git(self.repo, "add", "-f", "--", os.path.basename(r.series_file))
        git(self.repo, "commit", "-q", "-m", "series outside the record folder")
        self.ok(r, "freeze")
        done = self.call(r, "run")
        self.assertEqual((done[0], done[2]), (0, ""), done)
        self.assertEqual(done[1].splitlines()[-1], "series: added row skills-top to %s" % r.shown)
        self.assertEqual(len(self.bytes_of(r).split(b"\n")), 4)

    def test_a6_a_series_folder_that_is_a_link_out_of_the_record_folder_is_message_12(self):
        away = os.path.join(self.tmp, "away")
        plans = os.path.join(self.record, "plans")
        # the plan is frozen below the series folder, which then becomes a link out of R, and
        # the plan is outside R
        r = self.make("a6", series_dir=plans)
        self.ok(r, "freeze")
        self.move_out(r)
        shutil.move(plans, away)
        os.symlink(away, plans)
        written = os.path.join(away, "s-a6.series.tsv")
        before = self.read(written)
        done = self.call(r, "run")
        # a mutant that keeps only the paths whose resolved text starts with R, before it
        # asks the check, drops this path and lets the run write through the link
        want = "refused: %s%s%s\n" % (r.series_file, ESCAPES, self.suffix(r))
        self.assertEqual(done, (1, "", want))
        self.assertFalse(r.exists(ab.READS_DIR))
        self.assertFalse(r.exists("result-1.txt"))
        self.assertEqual(self.read(written), before)

    def test_a9_an_unusable_config_stops_freeze_whatever_the_plan_names(self):
        for name, raw, reason in BREAKAGES[:2]:
            for number, where in enumerate((None, os.path.join(self.tmp, "else"))):
                with self.subTest(breakage=name, series=number):
                    self.put_cfg(self.record)
                    r = self.make("a9%s%d" % (name[:3], number), series_dir=where)
                    self.put_cfg(raw=raw)
                    done = self.direct(ab.freeze, r.plan_path)
                    # a freeze that did not look at the config at all would go through
                    self.assertEqual((done.exit_code, done.ran, done.error + "\n"),
                                     (2, False, message_6(reason)))
                    self.assertFalse(r.exists("plan.txt.freeze"))


class RefusedAfterTheResult(SeriesRecheck):
    def late(self, change):
        """A patch of the lock that lets the real lock be taken, then makes ``change``: the state
        the checks before the result could not see."""
        real = series._take_lock

        def taken_then_changed(f, started):
            fd = real(f, started)
            change()
            return fd
        return mock.patch.object(series, "_take_lock", taken_then_changed)

    def late_refusal(self, name, change, undo, reason):
        r = self.make(name)
        self.ok(r, "freeze")
        before = self.bytes_of(r)
        want = "series: not written: %s%s" % (reason, TAIL)
        try:
            for step, result in (("run", "result-1.txt"), ("score", "result-2.txt")):
                done = self.call(r, step, patches=[self.late(change)])
                # exit 1, never 2; the result is kept; the line has neither "refused: " nor
                # "cannot run: " and no series-file suffix
                self.assertEqual(done[0], 1, done)
                self.assertEqual(done[2], "")
                self.assertEqual(done[1].splitlines()[-1], want)
                self.assertNotIn("refused:", want)
                self.assertNotIn("cannot run:", want)
                self.assertTrue(r.exists(result))
                self.assertEqual(self.bytes_of(r), before)
                undo()
        finally:
            undo()
        # the cause fixed, the next score adds the row
        done = self.call(r, "score")
        self.assertEqual((done[0], done[2]), (0, ""), done)
        self.assertEqual(done[1].splitlines()[-1], "series: added row skills-top to %s" % r.shown)
        self.assertTrue(r.exists("result-3.txt"))
        self.assertEqual(len(self.bytes_of(r).split(b"\n")), 4)

    def test_a8_a_refusal_after_the_result_keeps_it_and_exits_1_never_2(self):
        empty = self.empty_path()

        def lose_git():
            os.environ["PATH"] = empty
        with self.subTest(late="tracked"):
            self.late_refusal("a8t", self.track, self.untrack,
                              self.line9()[len("refused: "):])
        with self.subTest(late="git unrunnable"):
            # message 11 is exit 2 before the result exists; once it exists it is exit 1
            self.late_refusal("a8g", lose_git, lambda: None,
                              self.line11()[len("cannot run: "):])
        with self.subTest(late="not ignored"):
            self.late_refusal("a8n", self.stop_ignoring, lambda: self.put(
                os.path.join(self.repo, ".gitignore"), "rec/\n"),
                              self.line10()[len("refused: "):])

    def test_a7_a_lock_file_that_becomes_a_link_after_the_checks_is_not_taken(self):
        r = self.make("a7")
        self.ok(r, "freeze")
        before = self.bytes_of(r)
        lock = r.series_file + ".lock"
        target = self.put(os.path.join(self.tmp, "elsewhere.txt"), "not a lock\n")
        real = series._take_lock

        def link_then_take(f, started):
            os.symlink(target, lock)
            return real(f, started)
        done = self.call(r, "run", patches=[mock.patch.object(series, "_take_lock",
                                                                link_then_take)])
        self.assertEqual(done[0], 1, done)
        self.assertEqual(done[2], "")
        self.assertEqual(done[1].splitlines()[-1],
                         "series: not written: cannot take %s.lock: not a regular file"
                         % printed_path(r.shown))
        self.assertTrue(r.exists("result-1.txt"))
        self.assertEqual(self.bytes_of(r), before)
        self.assertEqual(self.read(target), b"not a lock\n")
        self.assertTrue(os.path.islink(lock))


class WhereTheCheckIsMade(SeriesRecheck):
    def test_a9b_the_environment_main_is_given_reaches_the_series_check(self):
        self.track()
        r = self.move_out(self.make("a9b"))
        env = self.env()
        err = io.StringIO()
        # this process's own environment names no config; main is handed the one that does
        with mock.patch.dict(os.environ, {"CTR_CONFIG_DIR": os.path.join(self.tmp, "none")}):
            with mock.patch.object(sys, "stderr", err), \
                    mock.patch.object(sys, "stdout", io.StringIO()):
                code = cli.main(["ab", "freeze", r.plan_path], env)
        # a series check that read os.environ would find no config and let the freeze go
        self.assertEqual((code, err.getvalue()), (1, self.line9() + self.suffix(r) + "\n"))
        self.assertFalse(r.exists("plan.txt.freeze"))

    def test_no_series_means_no_series_re_check(self):
        calls = mock.Mock(wraps=write_guard.recheck)
        plain = self.make("plain", series=None)
        with_series = self.make("with")
        with mock.patch.object(write_guard, "recheck", calls):
            self.assertEqual(self.call(plain, "freeze")[0], 0)
            after_plain = calls.call_count
            self.assertEqual(self.call(with_series, "freeze")[0], 0)
            after_series = calls.call_count - after_plain
        # the command line's own call is the only one for a plan without series
        self.assertEqual(after_plain, 1)
        # a plan with series adds its own targets and the three series paths
        self.assertEqual(after_series, 3)


if __name__ == "__main__":
    unittest.main()
