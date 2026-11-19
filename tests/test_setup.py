"""Tests for ``track-record setup``, by case number. All data here is invented.

Every case runs with CTR_CONFIG_DIR, HOME and the working directory set to fresh temporary
folders, and with git's global and system configuration pointed at the null device, so no
case reads or writes a real config or is changed by the user's own ignore file. Terminal
input is supplied by a pseudo-terminal."""

import hashlib
import json
import os
import select
import stat
import subprocess
import sys
import tempfile
import termios
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import cli  # noqa: E402
from tests.test_record_folder import git, git_env, make_repo, write  # noqa: E402

CMD = [sys.executable, "-m", "career_track_record", "setup"]
LAYOUT = ("sources", "postings", "drafts", "plans")
SUMMARY_TAIL = (
    "  sources/   old résumés, letters and notes you collect here; no command looks here yet\n"
    "  postings/  saved job postings; keywords looks here\n"
    "  drafts/    your own document versions, kept here if you like; no command looks here yet\n"
    "  plans/     frozen plans for ab and panel, kept here if you like; no command looks here "
    "yet\n"
    "Create these in your record folder when you need them; the commands look for them "
    "there:\n"
    "  barred-list.txt   your barred wording list (barred)\n"
    "  claims-list.txt   your approved claims (claims)\n"
    "  tone-rules.json   your tone rules (tone; the shipped rules are used without it)\n"
    "  terms.tsv         your keyword terms (keywords)\n"
    'next: write barred-list.txt in your record folder, then run: track-record barred '
    '--control "Your Name" FILE; see docs/guides/barred.md\n')
TITLE = "Where should your record folder be?\n"
ASKED = "; re-run setup and choose 1"
TRACKED_ASKED = ASKED
FOLDER_TRACKED = "; move the record folder out of git, or stop git tracking the files in it"
FOLDER_IGNORED = "; move the record folder out of git, or have git ignore it"
WARNING = ('Files in this folder stay private only while git ignores it. Do not run '
           '"git add -f" or "git clean -x" on it, and a fresh clone will not carry it.\n')
# A name holding a line feed, a carriage return, a tab, ESC, U+2028, U+202E and a backslash.
ODD = "a\nb\rc\td" + chr(0x1B) + "e" + chr(0x2028) + "f" + chr(0x202E) + "g\\h"
ODD_SHOWN = "a\\nb\\rc\\td\\x1be\\u2028f\\u202eg\\\\h"


def snapshot(root):
    """Every path under root -> what it is (kind, mode, content hash or link target)."""
    found = {}
    for here, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(here, name)
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                found[path] = ("link", os.readlink(path))
            elif stat.S_ISDIR(info.st_mode):
                found[path] = ("dir", stat.S_IMODE(info.st_mode))
            else:
                with open(path, "rb") as handle:
                    digest = hashlib.sha256(handle.read()).hexdigest()
                found[path] = ("file", stat.S_IMODE(info.st_mode), digest)
    return found


def stray_changes(before, after, allowed):
    """The paths that differ between two snapshots and are neither inside an allowed path
    nor a folder newly made above one."""
    stray = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        inside = any(path == a or path.startswith(a + os.sep) for a in allowed)
        above = path not in before and any(a.startswith(path + os.sep) for a in allowed)
        if not (inside or above):
            stray.append(path)
    return stray


class Done:
    def __init__(self, code, out, err):
        self.code, self.out, self.err = code, out, err

    def __iter__(self):
        return iter((self.code, self.out, self.err))


class SetupCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, "home")
        self.cwd = os.path.join(self.tmp, "cwd")
        self.work = os.path.join(self.tmp, "work")
        self.cfg_dir = os.path.join(self.tmp, "cfg")
        self.cfg = os.path.join(self.cfg_dir, "config.json")
        for folder in (self.home, self.cwd, self.work):
            os.mkdir(folder)

    # -- running -----------------------------------------------------------------

    def p(self, *parts):
        return os.path.join(self.work, *parts)

    def env(self, path=None, extra=None):
        env = git_env()
        for name in ("CTR_CONFIG_DIR", "XDG_CONFIG_HOME", "BARRED_STRINGS_PATH"):
            env.pop(name, None)
        env.update({"CTR_CONFIG_DIR": self.cfg_dir, "HOME": self.home, "PYTHONPATH": SRC,
                    "PYTHONDONTWRITEBYTECODE": "1"})
        if path is not None:
            env["PATH"] = path
        env.update(extra or {})
        return env

    def command(self, args, umask=None, closed=False):
        if umask is None and not closed:
            return CMD + list(args)
        script = ('umask %s; ' % umask if umask else "") + 'exec "$0" "$@"' \
            + (" >&-" if closed else "")
        return ["/bin/sh", "-c", script] + CMD + list(args)

    def empty_path(self):
        folder = os.path.join(self.tmp, "no-programs")
        os.makedirs(folder, exist_ok=True)
        return folder

    def run_setup(self, *args, folder=None, writes=None, cwd=None, path=None, umask=None,
                  closed=False, extra=None, tty=None, tty_out=False, tty_err=True,
                  null_err=False, wait=60):
        """Run setup. ``writes`` lists the paths the run may change (default: the config
        folder and ``folder``); everything else under the temporary tree must be exactly
        as it was (the case S37 check, made for every run)."""
        allowed = [self.cfg_dir] + ([folder] if folder else []) if writes is None else writes
        before = snapshot(self.tmp)
        command = self.command(args, umask, closed)
        env = self.env(path, extra)
        if tty is None:
            proc = subprocess.run(command, cwd=cwd or self.cwd, env=env,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=60)
            done = Done(proc.returncode, proc.stdout.decode("utf-8"),
                        proc.stderr.decode("utf-8"))
        else:
            done = self.talk(command, tty, cwd or self.cwd, env, tty_out, tty_err, null_err,
                             wait)
        after = snapshot(self.tmp)
        self.assertEqual(stray_changes(before, after, allowed), [],
                         "setup changed something it may not write")
        return done

    def talk(self, command, keys, cwd, env, tty_out, tty_err, null_err, wait):
        """Run with a pseudo-terminal as standard input and, as asked, as standard output
        and standard error. A stream that is not the terminal is a pipe (standard error
        may be the null device). ``wait`` seconds without the run ending fails the test."""
        master, slave = os.openpty()
        # No echo: what the person types is not output of the command, and a test of what
        # standard output holds must not count it.
        attributes = termios.tcgetattr(slave)
        attributes[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attributes)
        err_stream = (slave if tty_err else subprocess.DEVNULL if null_err
                      else subprocess.PIPE)
        try:
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=slave,
                                    stdout=slave if tty_out else subprocess.PIPE,
                                    stderr=err_stream)
        finally:
            os.close(slave)
        seen = b""
        try:
            os.write(master, keys.encode("utf-8"))
            deadline = time.time() + wait
            while True:
                ready, _w, _x = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    seen += chunk
                elif proc.poll() is not None:
                    break
                if time.time() > deadline:
                    proc.kill()
                    proc.wait()
                    self.fail("setup did not finish in a terminal")
            proc.wait(timeout=30)
            text = seen.decode("utf-8").replace("\r\n", "\n")
            out = text if tty_out else proc.stdout.read().decode("utf-8")
            err = text if tty_err else (
                "" if null_err else proc.stderr.read().decode("utf-8"))
        finally:
            os.close(master)
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
        return Done(proc.returncode, out, err)

    # -- fixtures and answers ------------------------------------------------------

    def read_cfg(self):
        with open(self.cfg, encoding="utf-8") as handle:
            return json.load(handle)

    def cfg_bytes(self):
        with open(self.cfg, "rb") as handle:
            return handle.read()

    def put_cfg(self, folder=None, raw=None):
        os.makedirs(self.cfg_dir, exist_ok=True)
        data = raw if raw is not None else json.dumps(
            {"config-version": 1, "record-folder": folder})
        with open(self.cfg, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))

    def repo(self, name="repo", ignore=None):
        return make_repo(self.p(name), ignore=ignore)

    def summary(self, folder, old=None):
        text = "Setup done.\nconfig: %s\nrecord folder: %s\n" % (self.cfg, folder) + SUMMARY_TAIL
        if old is not None:
            text += "The old folder is unchanged: %s\n" % old
        return text

    def assertDone(self, done, folder, old=None):
        self.assertEqual((done.code, done.err), (0, ""), done.err)
        self.assertEqual(done.out, self.summary(folder, old))

    def assertLayout(self, folder):
        for name in LAYOUT:
            self.assertTrue(os.path.isdir(os.path.join(folder, name)), name)

    def assertRefused(self, done, code, err):
        self.assertEqual((done.code, done.out, done.err), (code, "", err + "\n"))

    def assertAsked(self, done, code, last):
        """A run that asked first: standard output empty, standard error holds the questions
        and ends with ``last``."""
        self.assertEqual((done.code, done.out), (code, ""), done.err)
        self.assertTrue(done.err.endswith(last + "\n"), done.err)

    def need_permission_checks(self):
        probe = os.path.join(self.tmp, "probe-ro")
        os.mkdir(probe, 0o500)
        self.addCleanup(os.chmod, probe, 0o700)
        if os.access(probe, os.W_OK):
            self.skipTest("this account can write to a read-only folder")

    def read_only(self, folder):
        os.chmod(folder, 0o500)
        self.addCleanup(os.chmod, folder, 0o700)


class SetupWithFolder(SetupCase):
    def test_s20_a_new_folder_outside_any_work_tree(self):
        folder = self.p("rec", "career")
        done = self.run_setup("--folder", folder, folder=folder, path=self.empty_path())
        self.assertDone(done, folder)
        self.assertEqual(self.read_cfg(), {"config-version": 1, "record-folder": folder})
        self.assertLayout(folder)
        self.assertEqual(sorted(os.listdir(folder)), sorted(LAYOUT))
        self.assertEqual(os.listdir(self.cfg_dir), ["config.json"])

    def test_s20_the_equals_form_a_tilde_and_a_relative_path(self):
        done = self.run_setup("--folder=~/from-home", folder=os.path.join(self.home, "from-home"))
        self.assertDone(done, os.path.join(self.home, "from-home"))
        self.assertEqual(self.read_cfg()["record-folder"], os.path.join(self.home, "from-home"))
        relative = os.path.join(self.cwd, "sub", "rec")
        done = self.run_setup("--folder", "sub/../sub/./rec", folder=relative)
        self.assertDone(done, relative, old=os.path.join(self.home, "from-home"))
        self.assertEqual(self.read_cfg()["record-folder"], relative)

    def test_s20_a_folder_that_already_exists_gains_only_the_layout(self):
        folder = self.p("existing")
        os.mkdir(folder)
        write(os.path.join(folder, "mine.txt"), "keep me\n")
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertDone(done, folder)
        self.assertEqual(sorted(os.listdir(folder)), sorted(LAYOUT + ("mine.txt",)))

    def test_s29_the_folder_is_a_file(self):
        folder = write(self.p("afile"))
        done = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(done, 2, "cannot run: setup: %s is not a folder" % folder)

    def test_s29_a_tracked_file_named_as_the_folder_is_message_5_not_9(self):
        repo = self.repo()
        write(os.path.join(repo, "tracked.txt"))
        git(repo, "add", "tracked.txt")
        folder = os.path.join(repo, "tracked.txt")
        done = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(done, 2, "cannot run: setup: %s is not a folder" % folder)

    def test_s29_a_dangling_link_is_not_a_folder(self):
        folder = self.p("dangling")
        os.symlink(self.p("nowhere"), folder)
        done = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(done, 2, "cannot run: setup: %s is not a folder" % folder)

    def test_s29a_a_read_only_parent_names_the_folder(self):
        self.need_permission_checks()
        parent = self.p("ro")
        os.mkdir(parent)
        self.read_only(parent)
        folder = os.path.join(parent, "rec")
        done = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(done, 2, "cannot run: setup: cannot create %s" % folder)
        self.assertFalse(os.path.exists(self.cfg))

    def test_s29a_a_file_where_a_layout_folder_should_be(self):
        folder = self.p("rec")
        os.mkdir(folder)
        blocker = write(os.path.join(folder, "postings"), "a file\n")
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertRefused(done, 2, "cannot run: setup: cannot create %s" % blocker)
        self.assertEqual(sorted(os.listdir(folder)), ["postings", "sources"])
        self.assertFalse(os.path.exists(self.cfg))
        os.unlink(blocker)
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertDone(done, folder)
        self.assertLayout(folder)

    def test_s29a_the_config_is_unchanged_when_creation_fails(self):
        old = self.p("old")
        self.run_setup("--folder", old, folder=old)
        before = self.cfg_bytes()
        folder = self.p("rec")
        os.mkdir(folder)
        write(os.path.join(folder, "plans"), "a file\n")
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertEqual(done.code, 2)
        self.assertEqual(self.cfg_bytes(), before)

    def test_s29b_message_13_shows_a_hostile_name_on_one_line(self):
        self.need_permission_checks()
        parent = self.p("ro")
        os.mkdir(parent)
        self.read_only(parent)
        name = "x\n\r" + chr(0x2028) + "y"
        done = self.run_setup("--folder", os.path.join(parent, name), writes=[])
        self.assertRefused(done, 2, "cannot run: setup: cannot create %s/x\\n\\r\\u2028y"
                           % parent)

    def test_s29b_messages_5_9_10_and_11_escape_the_folder_alike(self):
        shown = lambda base: base + "/" + ODD_SHOWN  # noqa: E731
        # 5: the odd name is a file.
        file_path = write(self.p(ODD))
        done = self.run_setup("--folder", file_path, writes=[])
        self.assertRefused(done, 2, "cannot run: setup: %s is not a folder" % shown(self.work))
        # 9, 10 and 11 in a work tree.
        repo = self.repo("tree")
        folder = os.path.join(repo, ODD)
        write(os.path.join(folder, "t.txt"))
        git(repo, "add", "-f", "--", ODD + "/t.txt")
        done = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(done, 1, "refused: %s holds files git tracks; pick a folder git "
                                    "does not track%s" % (shown(repo), FOLDER_TRACKED))
        other = os.path.join(repo, "n" + ODD)
        done = self.run_setup("--folder", other, writes=[])
        self.assertRefused(done, 1, "refused: %s/n%s is inside a git work tree and git does "
                                    "not ignore it%s" % (repo, ODD_SHOWN, FOLDER_IGNORED))
        done = self.run_setup("--folder", other, writes=[], path=self.empty_path())
        self.assertRefused(done, 2, "cannot run: cannot tell whether %s/n%s is tracked "
                                    "(git was not found)" % (repo, ODD_SHOWN))


class TrackedFolderCases(SetupCase):
    def test_s24_a_tracked_file_under_the_folder(self):
        old = self.p("old")
        self.run_setup("--folder", old, folder=old)
        before = self.cfg_bytes()
        repo = self.repo()
        write(os.path.join(repo, "rec", "a.txt"))
        git(repo, "add", "rec/a.txt")
        folder = os.path.join(repo, "rec")
        done = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(done, 1, "refused: %s holds files git tracks; pick a folder git "
                                    "does not track%s" % (folder, FOLDER_TRACKED))
        self.assertEqual(self.cfg_bytes(), before)
        self.assertEqual(os.listdir(folder), ["a.txt"])

    def test_s25_ignored_by_gitignore_but_holding_a_force_added_file(self):
        repo = self.repo(ignore="rec/\n")
        write(os.path.join(repo, "rec", "kept.txt"))
        git(repo, "add", "-f", "rec/kept.txt")
        folder = os.path.join(repo, "rec")
        done = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(done, 1, "refused: %s holds files git tracks; pick a folder git "
                                    "does not track%s" % (folder, FOLDER_TRACKED))

    def test_s25a_a_probe_like_name_ignored_does_not_pass_an_ordinary_folder(self):
        for number, rule in enumerate((".track-record-probe", "*.py[cod]")):
            for existing in (True, False):
                with self.subTest(rule=rule, existing=existing):
                    repo = self.repo("r%d%d" % (existing, number), ignore=rule + "\n")
                    folder = os.path.join(repo, "rec")
                    if existing:
                        write(os.path.join(folder, "private-record.txt"))
                    before = os.listdir(folder) if existing else None
                    done = self.run_setup("--folder", folder, writes=[])
                    self.assertRefused(done, 1, "refused: %s is inside a git work tree and "
                                                "git does not ignore it%s" % (folder, FOLDER_IGNORED))
                    self.assertEqual(os.listdir(folder) if existing else None, before)
                    self.assertFalse(os.path.exists(self.cfg))

    def test_s26_ignored_by_git_info_exclude_alone(self):
        repo = self.repo()
        with open(os.path.join(repo, ".git", "info", "exclude"), "a") as handle:
            handle.write("hidden/\n")
        folder = os.path.join(repo, "hidden")
        before_git = snapshot(os.path.join(repo, ".git"))
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertDone(done, folder)
        self.assertEqual(snapshot(os.path.join(repo, ".git")), before_git)
        self.assertEqual(git(repo, "status", "--porcelain"), "")

    def test_s27_a_link_outside_any_tree_into_a_tree_where_the_target_is_not_ignored(self):
        repo = self.repo()
        target = os.path.join(repo, "target")
        os.mkdir(target)
        link = self.p("link-out")
        os.symlink(target, link)
        done = self.run_setup("--folder", link, writes=[])
        self.assertRefused(done, 1, "refused: %s is inside a git work tree and git does not "
                                    "ignore it%s" % (link, FOLDER_IGNORED))
        self.assertEqual(os.listdir(target), [])

    def test_s28_git_missing_inside_a_work_tree_fails_closed(self):
        repo = self.repo(ignore="rec/\n")
        folder = os.path.join(repo, "rec")
        done = self.run_setup("--folder", folder, writes=[], path=self.empty_path())
        self.assertRefused(done, 2, "cannot run: cannot tell whether %s is tracked (git was "
                                    "not found)" % folder)
        self.assertFalse(os.path.exists(folder))

    def test_s28_git_missing_outside_any_work_tree_is_allowed(self):
        folder = self.p("plain", "rec")
        done = self.run_setup("--folder", folder, folder=folder, path=self.empty_path())
        self.assertDone(done, folder)

    def test_s28_a_broken_git_entry_cannot_tell(self):
        broken = self.p("broken")
        os.makedirs(os.path.join(broken, ".git"))
        folder = os.path.join(broken, "rec")
        done = self.run_setup("--folder", folder, writes=[])
        self.assertEqual((done.code, done.out), (2, ""))
        self.assertRegex(done.err, r"^cannot run: cannot tell whether .* is tracked "
                                   r"\(git [a-z -]+ exited \d+\)\n\Z")


class TerminalCases(SetupCase):
    def test_s21_no_folder_and_no_terminal(self):
        done = self.run_setup(writes=[])
        self.assertRefused(done, 2, "cannot run: setup needs --folder when it is not run in "
                                    "a terminal")
        self.assertFalse(os.path.exists(self.cfg_dir))

    def test_s21_a_terminal_on_one_side_only_is_not_a_terminal(self):
        message = "cannot run: setup needs --folder when it is not run in a terminal"
        # Standard input a terminal, standard output and standard error pipes.
        done = self.run_setup(writes=[], tty="\n", tty_err=False)
        self.assertRefused(done, 2, message)
        done = self.run_setup(writes=[], closed=True)
        self.assertEqual((done.code, done.out, done.err), (2, "", message + "\n"))

    def test_s21_standard_error_that_is_not_a_terminal_is_not_asked_on(self):
        message = "cannot run: setup needs --folder when it is not run in a terminal"
        # Standard input and standard output terminals, standard error a pipe.
        done = self.run_setup(writes=[], tty="1\n", tty_out=True, tty_err=False, wait=20)
        self.assertEqual((done.code, done.err), (2, message + "\n"))
        self.assertFalse(os.path.exists(self.cfg_dir))
        # Standard error the null device (setup 2>/dev/null): the same exit, no wait.
        done = self.run_setup(writes=[], tty="1\n", tty_out=True, tty_err=False,
                              null_err=True, wait=20)
        self.assertEqual(done.code, 2)
        self.assertFalse(os.path.exists(self.cfg_dir))

    def test_s22_enter_at_choice_takes_the_default(self):
        folder = os.path.join(self.home, "career-record")
        done = self.run_setup(tty="\n", folder=folder)
        self.assertEqual(done.code, 0, done.err)
        self.assertIn(TITLE +
                      "  1. A folder outside any git repository (recommended: git pushes only "
                      "files inside a repository): %s\n"
                      "  2. A folder here, kept out of git (for people working inside a clone "
                      "of this project): %s/my-record\n"
                      "  3. Another folder: you type its path\n"
                      "Choice [1]: " % (folder, self.cwd), done.err)
        self.assertNotIn(WARNING, done.err)
        self.assertEqual(done.out, self.summary(folder))
        self.assertEqual(self.read_cfg()["record-folder"], folder)
        self.assertLayout(folder)

    def test_s22_the_answer_1_is_the_default_too(self):
        folder = os.path.join(self.home, "career-record")
        done = self.run_setup(tty=" 1 \n", folder=folder)
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(self.read_cfg()["record-folder"], folder)

    def test_s22_option_3_asks_for_a_path(self):
        folder = self.p("typed", "here")
        done = self.run_setup(tty="3\n%s\n" % folder, folder=folder)
        self.assertEqual(done.code, 0, done.err)
        self.assertIn("Path: ", done.err)
        self.assertNotIn(WARNING, done.err)
        self.assertEqual(self.read_cfg()["record-folder"], folder)

    def test_s22_option_3_expands_a_tilde_and_makes_a_relative_path_absolute(self):
        done = self.run_setup(tty="3\n~/tilde-rec\n", folder=os.path.join(self.home, "tilde-rec"))
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(self.read_cfg()["record-folder"], os.path.join(self.home, "tilde-rec"))

    def test_s22_a_bad_answer_is_asked_again_up_to_three_times(self):
        folder = os.path.join(self.home, "career-record")
        done = self.run_setup(tty="x\n7\n\n", folder=folder)
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(done.err.count("Not a choice.\n"), 2)
        done = self.run_setup(tty="x\n7\nzero\n", writes=[])
        self.assertAsked(done, 2, "cannot run: setup: no valid answer")
        self.assertEqual(done.err.count("Not a choice.\n"), 3)

    def test_s22_an_empty_path_at_option_3_is_a_bad_answer(self):
        done = self.run_setup(tty="3\n\n3\n\n3\n\n", writes=[])
        self.assertAsked(done, 2, "cannot run: setup: no valid answer")

    def test_s22_the_end_of_input_is_no_valid_answer(self):
        done = self.run_setup(tty="\x04", writes=[])
        self.assertAsked(done, 2, "cannot run: setup: no valid answer")

    def test_s23_option_2_in_a_repository_that_ignores_my_record(self):
        repo = self.repo(ignore="my-record/\n")
        folder = os.path.join(repo, "my-record")
        done = self.run_setup(tty="2\n", folder=folder, cwd=repo)
        self.assertEqual(done.code, 0, done.err)
        self.assertIn(WARNING, done.err)
        self.assertNotIn(WARNING, done.out)
        self.assertEqual(done.out, self.summary(folder))
        self.assertLayout(folder)
        self.assertEqual(git(repo, "status", "--porcelain"), "")
        # After git add -f of a file in it, a re-run refuses (the residual risk).
        write(os.path.join(folder, "slip.txt"))
        git(repo, "add", "-f", "my-record/slip.txt")
        again = self.run_setup("--folder", folder, writes=[])
        self.assertRefused(again, 1, "refused: %s holds files git tracks; pick a folder git "
                                     "does not track%s" % (folder, FOLDER_TRACKED))

    def test_s23_option_2_in_a_repository_without_the_line(self):
        repo = self.repo()
        done = self.run_setup(tty="2\n", writes=[], cwd=repo)
        self.assertAsked(done, 1, "refused: %s/my-record is inside a git work tree and git "
                                  "does not ignore it%s" % (repo, ASKED))
        self.assertIn(WARNING, done.err)
        self.assertFalse(os.path.exists(os.path.join(repo, "my-record")))
        self.assertFalse(os.path.exists(self.cfg_dir))

    def test_s41_an_exit_2_after_a_question_leaves_standard_output_empty(self):
        done = self.run_setup(tty="x\n7\nzero\n", writes=[])
        self.assertEqual((done.code, done.out), (2, ""))
        self.assertTrue(done.err.startswith(TITLE), done.err)
        self.assertEqual(done.err.count("Choice [1]: "), 3)
        self.assertEqual(done.err.count("Not a choice.\n"), 3)
        self.assertTrue(done.err.endswith("cannot run: setup: no valid answer\n"))

    def test_s41_an_exit_1_after_option_2_leaves_standard_output_empty(self):
        repo = self.repo()
        done = self.run_setup(tty="2\n", writes=[], cwd=repo)
        self.assertEqual((done.code, done.out), (1, ""))
        self.assertIn(WARNING, done.err)
        self.assertTrue(done.err.endswith("does not ignore it%s\n" % ASKED), done.err)

    def test_s41_an_exit_0_has_the_summary_on_standard_output_and_the_question_on_error(self):
        folder = os.path.join(self.home, "career-record")
        done = self.run_setup(tty="\n", folder=folder)
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(done.out, self.summary(folder))
        self.assertTrue(done.err.startswith(TITLE))
        self.assertTrue(done.err.endswith("Choice [1]: "), done.err)

    def test_s23_the_repository_s_own_gitignore_line_is_one_line_my_record_slash(self):
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        self.assertEqual(lines.count("my-record/"), 1)


class SummaryCases(SetupCase):
    def test_s42_the_summary_is_these_lines_exactly(self):
        folder = self.p("rec")
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertEqual((done.code, done.err), (0, ""))
        self.assertEqual(done.out, (
            "Setup done.\n"
            "config: %s\n"
            "record folder: %s\n"
            "  sources/   old résumés, letters and notes you collect here; no command looks "
            "here yet\n"
            "  postings/  saved job postings; keywords looks here\n"
            "  drafts/    your own document versions, kept here if you like; no command looks "
            "here yet\n"
            "  plans/     frozen plans for ab and panel, kept here if you like; no command "
            "looks here yet\n"
            "Create these in your record folder when you need them; the commands look for "
            "them there:\n"
            "  barred-list.txt   your barred wording list (barred)\n"
            "  claims-list.txt   your approved claims (claims)\n"
            "  tone-rules.json   your tone rules (tone; the shipped rules are used without "
            "it)\n"
            "  terms.tsv         your keyword terms (keywords)\n"
            "next: write barred-list.txt in your record folder, then run: track-record "
            "barred --control \"Your Name\" FILE; see docs/guides/barred.md\n") % (self.cfg, folder))

    def test_s42_the_next_line_points_at_a_guide_that_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "docs", "guides", "barred.md")))

    def test_s42_the_question_and_the_prompts_stay_on_standard_error(self):
        folder = os.path.join(self.home, "career-record")
        done = self.run_setup(tty="\n", folder=folder)
        self.assertEqual(done.code, 0, done.err)
        self.assertNotIn("Choice", done.out)
        self.assertNotIn("Where should", done.out)
        self.assertTrue(done.out.startswith("Setup done.\n"))
        self.assertTrue(done.out.endswith("; see docs/guides/barred.md\n"))

    def test_s42_no_text_the_person_reads_says_your_files(self):
        done = self.run_setup("-h", writes=[])
        self.assertIn("record folder", done.out)
        self.assertNotIn("your files", done.out)


class SuffixCases(SetupCase):
    """The end of messages 9 and 10 depends on who asks."""

    def test_s43_setup_with_folder_and_setup_asked_end_differently(self):
        tracked = self.repo("tracked")
        write(os.path.join(tracked, "rec", "a.txt"))
        git(tracked, "add", "rec/a.txt")
        loose = self.repo("loose")
        base9 = "refused: %s holds files git tracks; pick a folder git does not track"
        base10 = "refused: %s is inside a git work tree and git does not ignore it"
        folder9 = os.path.join(tracked, "rec")
        folder10 = os.path.join(loose, "rec")
        done = self.run_setup("--folder", folder9, writes=[])
        self.assertRefused(done, 1, base9 % folder9 + FOLDER_TRACKED)
        self.assertNotIn("choose 1", done.err)
        done = self.run_setup("--folder", folder10, writes=[])
        self.assertRefused(done, 1, base10 % folder10 + FOLDER_IGNORED)
        self.assertNotIn("choose 1", done.err)
        # Asked its question: option 2 from a work tree that does not ignore my-record/.
        done = self.run_setup(tty="2\n", writes=[], cwd=loose)
        self.assertAsked(done, 1, base10 % os.path.join(loose, "my-record") + ASKED)
        # Asked, and the folder it keeps is now tracked.
        self.put_cfg(folder9)
        done = self.run_setup(tty="\n", writes=[])
        self.assertAsked(done, 1, base9 % folder9 + ASKED)


class RerunCases(SetupCase):
    def first(self, folder=None):
        folder = folder or self.p("rec")
        self.run_setup("--folder", folder, folder=folder)
        return folder

    def test_s30_enter_at_keep_it_keeps_the_folder_and_the_config_bytes(self):
        folder = self.first()
        before = self.cfg_bytes()
        os.rmdir(os.path.join(folder, "drafts"))
        mine = write(os.path.join(folder, "sources", "mine.txt"), "mine\n")
        done = self.run_setup(tty="\n", writes=[folder])
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(done.err, "Record folder: %s\nKeep it? [Y/n] " % folder)
        self.assertEqual(done.out, self.summary(folder))
        self.assertEqual(self.cfg_bytes(), before)
        self.assertTrue(os.path.isdir(os.path.join(folder, "drafts")))
        with open(mine) as handle:
            self.assertEqual(handle.read(), "mine\n")

    def test_s30_y_keeps_it_too(self):
        folder = self.first()
        done = self.run_setup(tty="Y\n", writes=[folder])
        self.assertEqual(done.code, 0, done.err)
        done = self.run_setup(tty="y\n", writes=[folder])
        self.assertEqual(done.code, 0, done.err)

    def test_s30_the_same_folder_with_folder_asks_nothing_and_keeps_the_bytes(self):
        folder = self.first()
        before = self.cfg_bytes()
        os.rmdir(os.path.join(folder, "plans"))
        done = self.run_setup("--folder", folder, writes=[folder])
        self.assertDone(done, folder)
        self.assertEqual(self.cfg_bytes(), before)
        self.assertTrue(os.path.isdir(os.path.join(folder, "plans")))

    def test_s30_a_kept_folder_is_checked_again(self):
        repo = self.repo(ignore="rec/\n")
        folder = os.path.join(repo, "rec")
        self.first(folder)
        write(os.path.join(folder, "slip.txt"))
        git(repo, "add", "-f", "rec/slip.txt")
        done = self.run_setup(tty="\n", writes=[])
        self.assertAsked(done, 1, "refused: %s holds files git tracks; pick a folder git "
                                  "does not track%s" % (folder, ASKED))

    def test_s30_a_bad_answer_to_keep_it_is_asked_again_then_refused(self):
        folder = self.first()
        done = self.run_setup(tty="maybe\nx\nq\n", writes=[])
        self.assertAsked(done, 2, "cannot run: setup: no valid answer")
        done = self.run_setup(tty="maybe\n\n", writes=[folder])
        self.assertEqual(done.code, 0, done.err)

    def test_s31_a_different_folder_replaces_the_config_and_leaves_the_old_one(self):
        old = self.first()
        write(os.path.join(old, "sources", "old.txt"), "old\n")
        new = self.p("new")
        done = self.run_setup("--folder", new, folder=new)
        self.assertDone(done, new, old=old)
        self.assertEqual(self.read_cfg()["record-folder"], new)
        with open(os.path.join(old, "sources", "old.txt")) as handle:
            self.assertEqual(handle.read(), "old\n")
        self.assertEqual(sorted(os.listdir(old)), sorted(LAYOUT))

    def test_s31_n_at_keep_it_goes_on_to_the_question(self):
        old = self.first()
        new = self.p("other")
        done = self.run_setup(tty="n\n3\n%s\n" % new, folder=new)
        self.assertEqual(done.code, 0, done.err)
        self.assertIn(TITLE, done.err)
        self.assertEqual(done.out, self.summary(new, old=old))
        self.assertEqual(self.read_cfg()["record-folder"], new)

    def test_s31_n_then_the_same_folder_is_a_keep(self):
        old = self.first()
        before = self.cfg_bytes()
        done = self.run_setup(tty="N\n3\n%s\n" % old, writes=[old])
        self.assertEqual(done.code, 0, done.err)
        self.assertNotIn("The old folder is unchanged", done.out)
        self.assertEqual(self.cfg_bytes(), before)

    def test_s32_an_invalid_config_without_folder_is_message_7(self):
        for name, raw in (("unknown key", '{"config-version": 1, "recrod-folder": "/a"}'),
                          ("not JSON", "nope"),
                          ("version 2", '{"config-version": 2, "record-folder": "/a"}'),
                          ("relative", '{"config-version": 1, "record-folder": "a"}')):
            with self.subTest(name):
                self.put_cfg(raw=raw)
                before = self.cfg_bytes()
                done = self.run_setup(tty="\n", writes=[])
                self.assertEqual(done.code, 2)
                self.assertTrue(done.err.startswith(
                    "cannot run: setup: the config is not valid ("), done.err)
                self.assertTrue(done.err.endswith("); give --folder to replace it\n"),
                                done.err)
                self.assertEqual(done.err.count("\n"), 1)
                self.assertEqual(self.cfg_bytes(), before)

    def test_s32_message_7_names_the_reason_exactly(self):
        self.put_cfg(raw='{"config-version": 1, "recrod-folder": "/a"}')
        done = self.run_setup(tty="\n", writes=[])
        self.assertEqual(done.err, "cannot run: setup: the config is not valid (unknown key "
                                   "recrod-folder); give --folder to replace it\n")

    def test_s32_with_folder_an_invalid_config_is_replaced(self):
        self.put_cfg(raw='{"config-version": 1, "recrod-folder": "/a"}')
        folder = self.p("rec")
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertDone(done, folder)
        self.assertEqual(self.read_cfg(), {"config-version": 1, "record-folder": folder})

    def test_s32_a_config_that_is_not_utf8_is_replaced_with_folder(self):
        self.put_cfg(raw=b"\xff\xfe\x00")
        folder = self.p("rec")
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertDone(done, folder)

    def test_s33_a_config_folder_that_cannot_be_written_is_message_8(self):
        self.need_permission_checks()
        old = self.first(self.p("old"))
        before = self.cfg_bytes()
        self.read_only(self.cfg_dir)
        new = self.p("new")
        done = self.run_setup("--folder", new, folder=new)
        self.assertRefused(done, 2, "cannot run: setup: cannot write the config")
        self.assertEqual(self.cfg_bytes(), before)
        self.assertEqual(sorted(os.listdir(self.cfg_dir)), ["config.json"])
        self.assertLayout(new)
        self.assertLayout(old)

    def test_s33_a_config_folder_that_cannot_be_made_is_message_8(self):
        blocker = write(os.path.join(self.tmp, "blocker"))
        folder = self.p("rec")
        done = self.run_setup("--folder", folder, folder=folder,
                              extra={"CTR_CONFIG_DIR": os.path.join(blocker, "sub")})
        self.assertRefused(done, 2, "cannot run: setup: cannot write the config")

    def test_s33_no_config_is_written_when_the_folder_is_refused(self):
        repo = self.repo()
        done = self.run_setup("--folder", os.path.join(repo, "rec"), writes=[])
        self.assertEqual(done.code, 1)
        self.assertFalse(os.path.exists(self.cfg_dir))


class ShowCases(SetupCase):
    def test_s34_a_valid_config_shows_seven_lines_and_writes_nothing(self):
        folder = self.p("rec")
        self.run_setup("--folder", folder, folder=folder)
        done = self.run_setup("--show", writes=[])
        self.assertEqual((done.code, done.err), (0, ""))
        self.assertEqual(done.out, (
            "config: %s (found)\nrecord folder: %s (not checked)\n"
            "barred --list: %s/barred-list.txt (not checked)\n"
            "claims --list: %s/claims-list.txt (not checked)\n"
            "tone --rules: %s/tone-rules.json (not checked)\n"
            "keywords --postings: %s/postings (not checked)\n"
            "keywords --terms: %s/terms.tsv (not checked)\n")
            % ((self.cfg,) + (folder,) * 6))
        self.assertEqual(len(done.out.splitlines()), 7)

    def test_s34_the_paths_are_not_tested_and_the_variable_is_not_shown(self):
        self.put_cfg(self.p("nowhere"))
        done = self.run_setup("--show", writes=[], extra={"BARRED_STRINGS_PATH": "/x/list"})
        self.assertEqual(done.code, 0)
        self.assertNotIn("/x/list", done.out)
        self.assertIn("barred --list: %s/barred-list.txt (not checked)\n" % self.p("nowhere"),
                      done.out)
        self.assertFalse(os.path.exists(self.p("nowhere")))

    def test_s34_a_hostile_folder_is_escaped_on_one_line_each(self):
        self.put_cfg(os.path.join(self.tmp, ODD))
        done = self.run_setup("--show", writes=[])
        self.assertEqual(done.code, 0)
        self.assertEqual(len(done.out.splitlines()), 7)
        self.assertIn("record folder: %s/%s (not checked)\n" % (self.tmp, ODD_SHOWN), done.out)

    def test_s34a_no_config_file(self):
        done = self.run_setup("--show", writes=[])
        self.assertEqual((done.code, done.err), (0, ""))
        self.assertEqual(done.out, (
            "config: %s (not found)\nrecord folder: none\nbarred --list: none\n"
            "claims --list: none\ntone --rules: none\nkeywords --postings: none\n"
            "keywords --terms: none\n") % self.cfg)

    def test_s34b_an_invalid_config_is_message_6_on_standard_error(self):
        for name, raw, reason in (
                ("unknown key", '{"config-version": 1, "recrod-folder": "/a"}',
                 "unknown key recrod-folder"),
                ("repeated key", '{"config-version": 1, "record-folder": "/a", '
                                 '"record-folder": "/b"}', "repeated key record-folder"),
                ("version 2", '{"config-version": 2, "record-folder": "/a"}',
                 "config-version is from a newer version"),
                ("relative folder", '{"config-version": 1, "record-folder": "a"}',
                 "record-folder must be an absolute path"),
                ("non-string", '{"config-version": 1, "record-folder": 3}',
                 "record-folder must be a string"),
                ("not UTF-8", b'{"config-version": 1, "record-folder": "/a\xff"}',
                 "cannot read config")):
            with self.subTest(name):
                self.put_cfg(raw=raw)
                done = self.run_setup("--show", writes=[])
                self.assertRefused(done, 2, "cannot run: the track-record config is not "
                                            "usable (%s); run track-record setup --folder "
                                            "<folder>" % reason)

    def test_s34_show_reads_the_config_from_the_xdg_folder_when_no_override(self):
        xdg = os.path.join(self.tmp, "xdg")
        os.makedirs(os.path.join(xdg, "track-record"))
        with open(os.path.join(xdg, "track-record", "config.json"), "w") as handle:
            json.dump({"config-version": 1, "record-folder": "/Users/example/rec"}, handle)
        env = self.env(extra={"XDG_CONFIG_HOME": xdg})
        del env["CTR_CONFIG_DIR"]
        proc = subprocess.run(CMD + ["--show"], cwd=self.cwd, env=env, capture_output=True,
                              stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"record folder: /Users/example/rec (not checked)\n", proc.stdout)
        self.assertIn(("config: %s/track-record/config.json (found)" % xdg).encode(),
                      proc.stdout)


class UsageCases(SetupCase):
    def test_s35_option_misuse_is_one_cannot_run_line_and_nothing_else(self):
        cases = (
            (["--folder", "a", "--folder", "b"], "cannot run: setup: --folder given twice"),
            (["--folder"], "cannot run: setup: --folder needs a value"),
            (["--folder="], "cannot run: setup: --folder needs a value"),
            (["--folder", "--show"], "cannot run: setup: --folder needs a value"),
            (["--show", "--folder", "x"], "cannot run: setup: --show allows no other option"),
            (["--folder", "x", "--show"], "cannot run: setup: --show allows no other option"),
            (["--check", "x"], "cannot run: setup: unknown option --check"),
            (["--bogus"], "cannot run: setup: unknown option --bogus"),
            (["extra"], "cannot run: setup: extra argument extra"),
            (["--folder", "x", "extra"], "cannot run: setup: extra argument extra"),
            (["--show", "extra"], "cannot run: setup: extra argument extra"),
            (["--", "extra"], "cannot run: setup: extra argument extra"),
            (["--show", "--show"], "cannot run: setup: --show given twice"),
            (["--show=1"], "cannot run: setup: --show takes no value"),
            (["--"+ODD], "cannot run: setup: unknown option --%s" % ODD_SHOWN),
            ([ODD], "cannot run: setup: extra argument %s" % ODD_SHOWN),
        )
        for args, line in cases:
            with self.subTest(args=args):
                done = self.run_setup(*args, writes=[])
                self.assertRefused(done, 2, line)

    def test_s35_nothing_is_written_even_when_the_folder_would_have_been_good(self):
        done = self.run_setup("--folder", self.p("rec"), "extra", writes=[])
        self.assertEqual(done.code, 2)
        self.assertFalse(os.path.exists(self.p("rec")))
        self.assertFalse(os.path.exists(self.cfg_dir))

    def test_s36_standard_output_closed(self):
        done = self.run_setup("--show", writes=[], closed=True)
        self.assertEqual((done.code, done.out, done.err),
                         (2, "", "cannot run: cannot write output\n"))
        folder = self.p("rec")
        done = self.run_setup("--folder", folder, folder=folder, closed=True)
        self.assertEqual((done.code, done.out, done.err),
                         (2, "", "cannot run: cannot write output\n"))
        done = self.run_setup("-h", writes=[], closed=True)
        self.assertEqual((done.code, done.out, done.err),
                         (2, "", "cannot run: cannot write output\n"))

    def test_s36_standard_output_a_pipe_nobody_reads(self):
        r, w = os.pipe()
        os.close(r)
        try:
            proc = subprocess.run(CMD + ["--show"], cwd=self.cwd, env=self.env(),
                                  stdin=subprocess.DEVNULL, stdout=w,
                                  stderr=subprocess.PIPE)
        finally:
            os.close(w)
        self.assertEqual((proc.returncode, proc.stderr.decode()),
                         (2, "cannot run: cannot write output\n"))


class StaleCheckCases(SetupCase):
    def test_s37_the_check_itself_finds_a_stray_file(self):
        folder = self.p("rec")
        before = snapshot(self.tmp)
        os.makedirs(os.path.join(folder, "sources"))
        write(os.path.join(self.cwd, "stray.txt"))
        after = snapshot(self.tmp)
        self.assertEqual(stray_changes(before, after, [self.cfg_dir, folder]),
                         [os.path.join(self.cwd, "stray.txt")])

    def test_s37_a_changed_mode_or_a_changed_file_is_a_change(self):
        victim = write(os.path.join(self.cwd, "mine.txt"), "one\n")
        before = snapshot(self.tmp)
        write(victim, "two\n")
        self.assertEqual(stray_changes(before, snapshot(self.tmp), []), [victim])
        before = snapshot(self.tmp)
        os.chmod(victim, 0o600)
        self.assertEqual(stray_changes(before, snapshot(self.tmp), []), [victim])

    def test_s37_a_run_that_writes_nothing_leaves_the_tree_identical(self):
        before = snapshot(self.tmp)
        done = self.run_setup("--show", writes=[])
        self.assertEqual(done.code, 0)
        self.assertEqual(snapshot(self.tmp), before)

    def test_s37_a_run_in_a_work_tree_leaves_the_repository_untouched(self):
        repo = self.repo(ignore="my-record/\n")
        folder = os.path.join(repo, "my-record")
        before = snapshot(repo)
        done = self.run_setup("--folder", folder, folder=folder)
        self.assertEqual(done.code, 0, done.err)
        changed = [p for p in set(before) | set(snapshot(repo))
                   if before.get(p) != snapshot(repo).get(p)]
        self.assertTrue(all(p == folder or p.startswith(folder + os.sep) for p in changed),
                        changed)


class ModeCases(SetupCase):
    def mode(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)

    def test_s40_modes_under_both_umasks(self):
        for mask, parent_mode in (("022", 0o755), ("077", 0o700)):
            with self.subTest(umask=mask):
                base = self.p("m" + mask)
                folder = os.path.join(base, "parent", "rec")
                done = self.run_setup("--folder", folder, folder=base, umask=mask)
                self.assertEqual(done.code, 0, done.err)
                self.assertEqual(self.mode(folder), 0o700)
                for name in LAYOUT:
                    self.assertEqual(self.mode(os.path.join(folder, name)), 0o700, name)
                self.assertEqual(self.mode(self.cfg), 0o600)
                self.assertEqual(self.mode(os.path.join(base, "parent")), parent_mode)

    def test_s40_an_umask_that_takes_owner_bits_away_does_not_leave_a_folder_unusable(self):
        os.mkdir(self.cfg_dir, 0o700)
        folder = self.p("rec")
        done = self.run_setup("--folder", folder, folder=folder, umask="0277")
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(self.mode(folder), 0o700)
        for name in LAYOUT:
            self.assertEqual(self.mode(os.path.join(folder, name)), 0o700, name)
        self.assertEqual(self.mode(self.cfg), 0o600)

    def test_s40_an_existing_folder_keeps_its_mode_and_a_new_layout_folder_is_0700(self):
        folder = self.p("rec")
        os.mkdir(folder, 0o755)
        os.chmod(folder, 0o755)
        done = self.run_setup("--folder", folder, folder=folder, umask="022")
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(self.mode(folder), 0o755)
        os.rmdir(os.path.join(folder, "plans"))
        os.chmod(os.path.join(folder, "sources"), 0o750)
        done = self.run_setup("--folder", folder, folder=folder, umask="022")
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(self.mode(folder), 0o755)
        self.assertEqual(self.mode(os.path.join(folder, "plans")), 0o700)
        self.assertEqual(self.mode(os.path.join(folder, "sources")), 0o750)

    def test_s40_a_replaced_config_is_0600(self):
        first = self.p("first")
        self.run_setup("--folder", first, folder=first)
        os.chmod(self.cfg, 0o644)
        second = self.p("second")
        done = self.run_setup("--folder", second, folder=second, umask="000")
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(self.mode(self.cfg), 0o600)
        self.assertEqual(self.read_cfg()["record-folder"], second)

    def test_s40_the_config_folder_it_makes_is_not_made_wider_than_the_default(self):
        done = self.run_setup("--folder", self.p("rec"), folder=self.p("rec"), umask="077")
        self.assertEqual(done.code, 0, done.err)
        self.assertEqual(self.mode(self.cfg_dir), 0o700)


class ConfigLocationCases(SetupCase):
    def test_s38_ctr_config_dir_is_where_the_config_is_written_and_nowhere_else(self):
        xdg = os.path.join(self.tmp, "xdg")
        folder = self.p("rec")
        done = self.run_setup("--folder", folder, folder=folder, extra={"XDG_CONFIG_HOME": xdg})
        self.assertEqual(done.code, 0, done.err)
        self.assertTrue(os.path.isfile(self.cfg))
        self.assertFalse(os.path.exists(xdg))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".config")))

    def test_s38_unset_empty_or_relative_ctr_config_dir_gives_way_to_xdg_then_home(self):
        for value in (None, "", "relative"):
            with self.subTest(ctr=value):
                tmp = tempfile.mkdtemp(dir=self.tmp)
                xdg = os.path.join(tmp, "xdg")
                folder = os.path.join(tmp, "rec")
                env = self.env(extra={"XDG_CONFIG_HOME": xdg})
                if value is None:
                    del env["CTR_CONFIG_DIR"]
                else:
                    env["CTR_CONFIG_DIR"] = value
                proc = subprocess.run(CMD + ["--folder", folder], cwd=tmp, env=env,
                                      stdin=subprocess.DEVNULL, capture_output=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(os.path.isfile(os.path.join(xdg, "track-record",
                                                            "config.json")))
                self.assertFalse(os.path.exists(os.path.join(tmp, "relative")))

    def test_s38_with_neither_it_is_the_home_dot_config_folder(self):
        folder = self.p("rec")
        env = self.env()
        del env["CTR_CONFIG_DIR"]
        proc = subprocess.run(CMD + ["--folder", folder], cwd=self.cwd, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".config", "track-record",
                                                    "config.json")))


HELP = """\
usage: track-record setup [--folder PATH]
       track-record setup --show

Choose your record folder: ask once, write a small config naming it, and make the
folder and its four layout folders. It runs no check.

  --folder PATH  use PATH as the record folder and ask nothing
  --show         show the config and the folder each command would use
  -h, --help     show this summary and exit

config: $CTR_CONFIG_DIR/config.json, else $XDG_CONFIG_HOME/track-record/config.json,
    else ~/.config/track-record/config.json

exit: 0 done, kept or shown, 1 the folder is refused (git tracks it, or a work tree does
    not ignore it), 2 it cannot run
"""

EIGHT = """\
    keywords  scan saved job postings for terms
    barred    report wording from your own barred list
    tone      flag hype, hedges and filler in your copy
    ab        compare two versions of your copy with test readers
    claims    fail on sentences your claims list hasn't approved
    panel     read one version blind through named lenses
    record    check your record's tables against rules you declare
    drafts    check a file of a document's versions, or extract one
"""


class HelpCases(SetupCase):
    def test_s39_setup_help_is_the_pinned_text(self):
        for flag in ("-h", "--help"):
            with self.subTest(flag):
                done = self.run_setup(flag, writes=[])
                self.assertEqual((done.code, done.out, done.err), (0, HELP, ""))

    def test_s39_setup_help_is_fixed_text_that_names_options_exit_codes_and_config(self):
        self.assertEqual(cli._SETUP_HELP, HELP)
        for needle in ("--folder PATH", "--show", "-h, --help", "exit: 0", "1 the folder is refused",
                       "2 it cannot run", "$CTR_CONFIG_DIR/config.json",
                       "$XDG_CONFIG_HOME/track-record/config.json",
                       "~/.config/track-record/config.json"):
            self.assertIn(needle, HELP)

    def test_s10_help_wins_over_other_arguments_and_reads_no_config(self):
        self.put_cfg(raw="not json at all")
        for args in (["-h"], ["--help"], ["--folder", "-h"], ["--show", "-h"],
                     ["-h", "--bogus"], ["--bogus", "--help"], ["extra", "-h"]):
            with self.subTest(args=args):
                done = self.run_setup(*args, writes=[])
                self.assertEqual((done.code, done.out, done.err), (0, HELP, ""))

    def test_s39_the_top_level_help_lists_the_eight_and_setup_apart(self):
        done = subprocess.run([sys.executable, "-m", "career_track_record", "--help"],
                              cwd=self.cwd, env=self.env(), capture_output=True,
                              stdin=subprocess.DEVNULL)
        text = done.stdout.decode("utf-8")
        self.assertEqual((done.returncode, done.stderr), (0, b""))
        # wrapped-compounds and parse sit between the eight and setup (tests/test_help_lines.py
        # pins the exact spacing); the long name widens every column, so compare by words.
        words = " ".join(text.split())
        self.assertIn(" ".join(EIGHT.split()) + " wrapped-compounds find hyphenated words "
                      "split across two lines in a PDF parse check what a text extractor gets from your résumé PDF "
                      "setup choose your record folder ", words)
        self.assertEqual(text.count("\n    setup "), 1)

    def test_a_name_that_only_starts_like_setup_is_not_setup(self):
        done = subprocess.run([sys.executable, "-m", "career_track_record", "setupx"],
                              cwd=self.cwd, env=self.env(), capture_output=True,
                              stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 2)
        self.assertIn(b"invalid choice: 'setupx'", done.stderr)


if __name__ == "__main__":
    unittest.main()
