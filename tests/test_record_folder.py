"""Tests for the tracked-folder decision, in throwaway git repositories. All data is invented.

Every git run here sets the global and system configuration to the null device, so the
user's own ignore file cannot change an answer."""

import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import record_folder  # noqa: E402


def git_env(extra=None):
    env = dict(os.environ)
    for name in [n for n in env if n.startswith("GIT_")]:
        del env[name]
    env.update({"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.invalid"})
    env.update(extra or {})
    return env


def git(folder, *args):
    done = subprocess.run(["git", "-C", folder] + list(args), env=git_env(),
                          stdin=subprocess.DEVNULL, capture_output=True, check=False)
    if done.returncode != 0:
        raise AssertionError("git %s failed: %r" % (" ".join(args), done.stderr))
    return done.stdout.decode("utf-8")


def make_repo(path, ignore=None):
    """A throwaway work tree at ``path`` with one commit; ``ignore`` is the .gitignore text."""
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q")
    with open(os.path.join(path, "README"), "w") as handle:
        handle.write("invented\n")
    paths = ["README"]
    if ignore is not None:
        with open(os.path.join(path, ".gitignore"), "w") as handle:
            handle.write(ignore)
        paths.append(".gitignore")
    git(path, "add", *paths)
    git(path, "commit", "-q", "-m", "first")
    return path


def write(path, text="invented\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    return path


class Repo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        env = git_env()
        patch = unittest.mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)


class DecideCase(Repo):
    def test_no_work_tree_is_allowed_and_runs_no_git(self):
        folder = self.p("plain", "record")
        with unittest.mock.patch.object(record_folder, "_git") as fake:
            verdict = record_folder.decide(folder)
        self.assertEqual(verdict.kind, record_folder.ALLOWED)
        fake.assert_not_called()
        self.assertFalse(os.path.exists(self.p("plain")))

    def test_an_ignored_folder_is_allowed_whether_or_not_it_exists(self):
        repo = make_repo(self.p("repo"), ignore="my-record/\n")
        self.assertTrue(record_folder.decide(os.path.join(repo, "my-record")).allowed)
        os.mkdir(os.path.join(repo, "my-record"))
        self.assertTrue(record_folder.decide(os.path.join(repo, "my-record")).allowed)

    def test_a_folder_git_does_not_ignore_is_refused(self):
        repo = make_repo(self.p("repo"))
        for sub in ("my-record", "deep/er/my-record"):
            verdict = record_folder.decide(os.path.join(repo, sub))
            self.assertEqual(verdict.kind, record_folder.NOT_IGNORED, sub)

    def test_a_tracked_file_under_the_folder_is_refused_even_when_ignored(self):
        repo = make_repo(self.p("repo"), ignore="my-record/\n")
        write(os.path.join(repo, "my-record", "kept.txt"))
        git(repo, "add", "-f", "my-record/kept.txt")
        verdict = record_folder.decide(os.path.join(repo, "my-record"))
        self.assertEqual(verdict.kind, record_folder.TRACKED)

    def test_git_location_variables_in_the_environment_do_not_change_the_verdict(self):
        repo = make_repo(self.p("repo"), ignore="mine/\n")
        os.mkdir(os.path.join(repo, "mine"))
        write(os.path.join(repo, "rec", "a.txt"))
        git(repo, "add", "rec/a.txt")
        other = make_repo(self.p("other"))
        wanted = {os.path.join(repo, "mine"): record_folder.ALLOWED,
                  os.path.join(repo, "rec"): record_folder.TRACKED,
                  os.path.join(repo, "free"): record_folder.NOT_IGNORED}
        for folder, kind in wanted.items():
            self.assertEqual(record_folder.decide(folder).kind, kind, folder)
        cases = {
            "GIT_DIR": {"GIT_DIR": os.path.join(other, ".git")},
            "GIT_WORK_TREE and GIT_INDEX_FILE": {
                "GIT_WORK_TREE": other,
                "GIT_INDEX_FILE": os.path.join(other, ".git", "index")},
            "GIT_COMMON_DIR": {"GIT_COMMON_DIR": os.path.join(other, ".git")},
        }
        for label, variables in cases.items():
            for folder, kind in wanted.items():
                with self.subTest(label, folder=os.path.basename(folder)):
                    with unittest.mock.patch.dict(os.environ, variables):
                        verdict = record_folder.decide(folder)
                    self.assertEqual(verdict.kind, kind)

    def test_the_scrubbed_environment_drops_exactly_the_location_variables(self):
        names = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                 "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
                 "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM"]
        planted = {name: "x" for name in names}
        planted.update({"GIT_CONFIG_COUNT": "0", "HTTPS_PROXY": "p", "PATH": os.environ["PATH"]})
        with unittest.mock.patch.dict(os.environ, planted):
            kept = record_folder.scrubbed_environment()
            expected = {k: v for k, v in os.environ.items() if k not in names}
        self.assertEqual(kept, expected)
        self.assertIn("GIT_CONFIG_GLOBAL", kept)

    def test_a_tracked_file_under_a_folder_in_a_tracked_tree_is_refused(self):
        repo = make_repo(self.p("repo"))
        write(os.path.join(repo, "rec", "a.txt"))
        git(repo, "add", "rec/a.txt")
        self.assertEqual(record_folder.decide(os.path.join(repo, "rec")).kind,
                         record_folder.TRACKED)

    def test_the_probe_like_name_does_not_pass_an_ordinary_folder(self):
        repo = make_repo(self.p("repo"), ignore=".track-record-probe\n")
        write(os.path.join(repo, "rec", "private-record.txt"))
        self.assertEqual(record_folder.decide(os.path.join(repo, "rec")).kind,
                         record_folder.NOT_IGNORED)

    def test_the_pyc_rule_does_not_pass_an_ordinary_folder(self):
        repo = make_repo(self.p("repo"), ignore="*.py[cod]\n")
        write(os.path.join(repo, "rec", "private-record.txt"))
        for existing in (True, False):
            folder = os.path.join(repo, "rec" if existing else "not-created")
            self.assertEqual(record_folder.decide(folder).kind, record_folder.NOT_IGNORED)

    def test_git_info_exclude_alone_allows_the_folder(self):
        repo = make_repo(self.p("repo"))
        with open(os.path.join(repo, ".git", "info", "exclude"), "a") as handle:
            handle.write("hidden-record/\n")
        self.assertTrue(record_folder.decide(os.path.join(repo, "hidden-record")).allowed)

    def test_a_link_outside_any_tree_is_seen_for_what_it_is(self):
        repo = make_repo(self.p("repo"))
        os.makedirs(os.path.join(repo, "target"))
        link = self.p("outside-link")
        os.symlink(os.path.join(repo, "target"), link)
        self.assertEqual(record_folder.decide(link).kind, record_folder.NOT_IGNORED)
        self.assertEqual(record_folder.decide(os.path.join(link, "new")).kind,
                         record_folder.NOT_IGNORED)

    def test_a_dangling_link_is_resolved_not_taken_for_a_missing_folder(self):
        repo = make_repo(self.p("repo"))
        link = self.p("dangling")
        os.symlink(os.path.join(repo, "not-yet"), link)
        self.assertEqual(record_folder.decide(link).kind, record_folder.NOT_IGNORED)

    def test_a_linked_work_tree_with_a_git_file_is_found(self):
        repo = make_repo(self.p("repo"))
        git(repo, "worktree", "add", "-q", self.p("linked"), "-b", "other")
        self.assertTrue(os.path.isfile(self.p("linked", ".git")))
        self.assertEqual(record_folder.decide(self.p("linked", "rec")).kind,
                         record_folder.NOT_IGNORED)

    def test_a_folder_name_with_glob_characters_is_taken_literally(self):
        repo = make_repo(self.p("repo"), ignore="/rec\\[1\\]/\n")
        os.makedirs(os.path.join(repo, "rec[1]"))
        write(os.path.join(repo, "rec1", "kept.txt"))
        git(repo, "add", "rec1/kept.txt")
        self.assertTrue(record_folder.decide(os.path.join(repo, "rec[1]")).allowed)
        os.makedirs(os.path.join(repo, "*"))
        self.assertEqual(record_folder.decide(os.path.join(repo, "*")).kind,
                         record_folder.NOT_IGNORED)

    def test_git_missing_fails_closed_inside_a_work_tree_only(self):
        repo = make_repo(self.p("repo"), ignore="my-record/\n")
        empty = self.p("empty-path")
        os.mkdir(empty)
        with unittest.mock.patch.dict(os.environ, {"PATH": empty}):
            inside = record_folder.decide(os.path.join(repo, "my-record"))
            outside = record_folder.decide(self.p("elsewhere", "rec"))
        self.assertEqual(inside.kind, record_folder.CANNOT_TELL)
        self.assertEqual(inside.reason, "git was not found")
        self.assertTrue(outside.allowed)

    def test_a_git_answer_other_than_zero_or_one_cannot_tell(self):
        repo = make_repo(self.p("repo"), ignore="my-record/\n")
        calls = iter([(0, b""), (128, b"")])
        with unittest.mock.patch.object(record_folder, "_git", lambda *a: next(calls)):
            verdict = record_folder.decide(os.path.join(repo, "my-record"))
        self.assertEqual((verdict.kind, verdict.reason),
                         (record_folder.CANNOT_TELL, "git check-ignore exited 128"))
        with unittest.mock.patch.object(record_folder, "_git", lambda *a: (128, b"")):
            verdict = record_folder.decide(os.path.join(repo, "my-record"))
        self.assertEqual((verdict.kind, verdict.reason),
                         (record_folder.CANNOT_TELL, "git ls-files exited 128"))

    def test_a_broken_dot_git_cannot_tell(self):
        broken = self.p("broken")
        os.makedirs(os.path.join(broken, ".git"))
        verdict = record_folder.decide(os.path.join(broken, "rec"))
        self.assertEqual(verdict.kind, record_folder.CANNOT_TELL)

    def test_a_git_that_times_out_cannot_tell(self):
        repo = make_repo(self.p("repo"))
        boom = subprocess.TimeoutExpired(["git"], 1)
        with unittest.mock.patch.object(subprocess, "run", side_effect=boom):
            verdict = record_folder.decide(os.path.join(repo, "rec"))
        self.assertEqual((verdict.kind, verdict.reason),
                         (record_folder.CANNOT_TELL, "git did not answer in time"))

    def test_deciding_creates_moves_and_deletes_nothing(self):
        repo = make_repo(self.p("repo"), ignore="my-record/\n")
        before = sorted(os.path.join(d, n) for d, ds, fs in os.walk(self.tmp)
                        for n in ds + fs if ".git" + os.sep not in os.path.join(d, n))
        for sub in ("my-record", "other", "deep/er"):
            record_folder.decide(os.path.join(repo, sub))
        after = sorted(os.path.join(d, n) for d, ds, fs in os.walk(self.tmp)
                       for n in ds + fs if ".git" + os.sep not in os.path.join(d, n))
        self.assertEqual(before, after)

    def test_the_verdict_names_the_folder_as_given(self):
        repo = make_repo(self.p("repo"))
        folder = os.path.join(repo, "rec")
        self.assertEqual(record_folder.decide(folder).folder, folder)

    def test_git_is_given_an_argument_list_and_no_shell(self):
        repo = make_repo(self.p("repo"))
        with unittest.mock.patch.object(subprocess, "run",
                                        wraps=subprocess.run) as spy:
            record_folder.decide(os.path.join(repo, "rec"))
        self.assertEqual(spy.call_count, 2)
        for call in spy.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:2], ["git", "-C"])
            self.assertNotIn("shell", call.kwargs)
        self.assertIn("--literal-pathspecs", spy.call_args_list[0].args[0])


class RefusalWording(unittest.TestCase):
    """Messages 9, 10 and 11 are built in one place; the caller picks the suffix (case S43:
    the six uses of messages 9 and 10)."""

    TRACKED = "refused: /r holds files git tracks; pick a folder git does not track"
    IGNORED = "refused: /r is inside a git work tree and git does not ignore it"

    def test_the_six_uses(self):
        tracked = record_folder.Verdict(record_folder.TRACKED, "/r")
        ignored = record_folder.Verdict(record_folder.NOT_IGNORED, "/r")
        stop = "; move the record folder out of git, or stop git tracking the files in it"
        have = "; move the record folder out of git, or have git ignore it"
        ask = "; re-run setup and choose 1"
        self.assertEqual(record_folder.refusal(tracked, asked=True), (1, self.TRACKED + ask))
        self.assertEqual(record_folder.refusal(tracked), (1, self.TRACKED + stop))
        self.assertEqual(record_folder.refusal(ignored, asked=True), (1, self.IGNORED + ask))
        self.assertEqual(record_folder.refusal(ignored), (1, self.IGNORED + have))

    def test_message_11_and_an_allowed_folder(self):
        cannot = record_folder.Verdict(record_folder.CANNOT_TELL, "/r", "git was not found")
        for asked in (True, False):
            self.assertEqual(record_folder.refusal(cannot, asked), (
                2, "cannot run: cannot tell whether /r is tracked (git was not found)"))
        self.assertIsNone(record_folder.refusal(record_folder.Verdict(
            record_folder.ALLOWED, "/r")))

    def test_the_folder_is_escaped_as_a_printed_path(self):
        verdict = record_folder.Verdict(record_folder.TRACKED, "/r/a\nb\x1b")
        line = record_folder.refusal(verdict)[1]
        self.assertEqual(line.count("\n"), 0)
        self.assertIn("/r/a\\nb\\x1b holds", line)


if __name__ == "__main__":
    unittest.main()
