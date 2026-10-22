"""Unit tests for ci/barred_strings.py. All strings here are invented."""

import ast
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from ci import barred_strings

CANARY = "barred-strings-canary-ab12cd34ef"
ENTRY_A = "zebra quartz"
ENTRY_B = "ember-gull"
LIST_TEXT = "\n".join([CANARY, ENTRY_A, ENTRY_B]) + "\n"

MSG_NO_LIST = (
    "barred-strings scan: no list: set the BARRED_STRINGS secret (CI) or "
    "BARRED_STRINGS_PATH (local); failing closed"
)
MSG_NOT_CANARY = (
    "barred-strings scan: entry 1 is not a canary (barred-strings-canary- plus at "
    "least 8 letters or digits); failing closed"
)
MSG_SELF_TEST = (
    "barred-strings scan: self-test failed: the matcher did not find the "
    "canary; failing closed"
)
MSG_CANARY_FLAG = (
    "barred-strings scan: entry 1 (the canary) cannot carry the word flag; "
    "failing closed"
)
MSG_LIST_MALFORMED_CI = (
    "barred-strings scan: the list is malformed; run the scan locally to see "
    "which entry; failing closed"
)
MSG_FORK = (
    "barred-strings scan: pull request from a fork: secrets are not available "
    "here, so the scan cannot run; failing closed"
)
MSG_FILE_IN_CI = (
    "barred-strings scan: BARRED_STRINGS_PATH is not accepted in CI; failing closed"
)
MSG_BOTH = (
    "barred-strings scan: set BARRED_STRINGS or BARRED_STRINGS_PATH, not both; "
    "failing closed"
)
MSG_FILE_IN_REPO = (
    "barred-strings scan: the list file must live outside the repository; "
    "failing closed"
)
MSG_SHALLOW = (
    "barred-strings scan: repository is shallow; fetch full history "
    "(fetch-depth: 0); failing closed"
)


class Case(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            os.environ,
            {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = os.path.realpath(tmp.name)
        self.counter = 0
        self.outputs = []

    # -- helpers ----------------------------------------------------------

    def git(self, cwd, *args, **extra_env):
        env = dict(os.environ)
        env.update(extra_env)
        proc = subprocess.run(
            ["git", "-C", cwd] + list(args),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.decode("utf-8").strip()

    def commit(self, repo, message, author="Test Author", committer=None,
               author_email="test@example.invalid",
               committer_email="test@example.invalid"):
        committer = committer or author
        self.git(
            repo, "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty",
            "-m", message,
            GIT_AUTHOR_NAME=author,
            GIT_AUTHOR_EMAIL=author_email,
            GIT_COMMITTER_NAME=committer,
            GIT_COMMITTER_EMAIL=committer_email,
        )
        return self.git(repo, "rev-parse", "HEAD")

    def make_repo(self, files=None, branch="main", message="first commit",
                  author="Test Author", committer=None,
                  author_email="test@example.invalid",
                  committer_email="test@example.invalid"):
        self.counter += 1
        repo = os.path.join(self.tmp, "repo%d" % self.counter)
        os.mkdir(repo)
        self.git(repo, "init", "-q", "-b", branch)
        for path, data in (files or {"notes.txt": "plain text\n"}).items():
            full = os.path.join(repo, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            if isinstance(data, str):
                data = data.encode("utf-8")
            with open(full, "wb") as handle:
                handle.write(data)
        self.git(repo, "add", "-A")
        sha = self.commit(repo, message, author, committer,
                          author_email, committer_email)
        return repo, sha

    def make_raw_commit_repo(self, branch="main"):
        """A repo whose only commit stores the bytes ff fe in its message."""
        self.counter += 1
        repo = os.path.join(self.tmp, "repo%d" % self.counter)
        os.mkdir(repo)
        self.git(repo, "init", "-q", "-b", branch)
        tree = self.git(repo, "mktree")
        body = (
            b"tree " + tree.encode("ascii") + b"\n"
            b"author Test Author <test@example.invalid> 1700000000 +0000\n"
            b"committer Test Author <test@example.invalid> 1700000000 +0000\n"
            b"\nsubject \xff\xfe bytes\n"
        )
        proc = subprocess.run(
            ["git", "-C", repo, "hash-object", "-t", "commit", "-w", "--stdin"],
            input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.raw_sha = proc.stdout.decode("ascii").strip()
        self.git(repo, "update-ref", "refs/heads/" + branch, self.raw_sha)
        return repo

    def write_file(self, repo, path, data):
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if isinstance(data, str):
            data = data.encode("utf-8")
        with open(full, "wb") as handle:
            handle.write(data)

    def blob_line(self, repo, ordinal, rev_path, shown, commit):
        """The expected content-hit line for the blob at rev_path."""
        blob = self.git(repo, "rev-parse", rev_path)
        return "entry %d matched in blob %s (first seen at %s in %s)" % (
            ordinal, blob[:12], shown, commit[:12])

    def run_main(self, repo, environ):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = barred_strings.main(["--repo", repo], environ)
        self.outputs.append((out.getvalue(), err.getvalue()))
        return status, out.getvalue(), err.getvalue()

    def run_local(self, repo, list_text=LIST_TEXT):
        return self.run_main(repo, {"BARRED_STRINGS": list_text})

    def lines(self, text):
        return text.splitlines()

    # -- matching ---------------------------------------------------------

    def test_hit_in_file(self):
        repo, sha = self.make_repo({"docs/page.txt": "see zebra quartz here\n"})
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            [self.blob_line(repo, 2, "HEAD:docs/page.txt", "docs/page.txt", sha),
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertEqual(err, "")

    def test_miss_is_clean(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 0)
        self.assertEqual(
            self.lines(out),
            ["barred-strings scan: clean (3 entries; 1 blobs; 1 paths; "
             "1 commits; branch checked)"],
        )

    def test_case_folding(self):
        self.assertEqual(barred_strings.find_hits("ZEBRA QUARTZ", [barred_strings.fold("Zebra Quartz")]), [1])
        self.assertEqual(barred_strings.find_hits("STRAßE", [barred_strings.fold("strasse")]), [1])

    def test_nfkc_folding(self):
        full = "ｚｅｂｒａ ｑｕａｒｔｚ"
        self.assertEqual(barred_strings.find_hits(full, [barred_strings.fold("zebra quartz")]), [1])
        self.assertEqual(barred_strings.find_hits("FINCH", [barred_strings.fold("ﬁnch")]), [1])
        # the reverse direction
        self.assertEqual(barred_strings.find_hits("zebra quartz", [barred_strings.fold(full)]), [1])
        self.assertEqual(barred_strings.find_hits("ﬁnch", [barred_strings.fold("FINCH")]), [1])

    def test_no_fuzzy_matching(self):
        entries = [barred_strings.fold("zebra quartz")]
        self.assertEqual(barred_strings.find_hits("zebra-quartz", entries), [])
        self.assertEqual(barred_strings.find_hits("zebraquartz", entries), [])

    def test_hit_in_commit_message(self):
        message = "subject line\n\nnotes: zebra quartz\twith a tab and 100% done\n"
        repo, sha = self.make_repo(message=message)
        status, out, _ = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in commit " + sha,
             "barred-strings scan: 1 hit(s); failing"],
        )

    def test_hit_in_author_name(self):
        repo, sha = self.make_repo(author="zebra quartz bench", committer="Test Author")
        status, out, _ = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(self.lines(out)[0], "entry 2 matched in commit " + sha)

    def test_hit_in_committer_name(self):
        repo, sha = self.make_repo(author="Test Author", committer="zebra quartz bench")
        status, out, _ = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(self.lines(out)[0], "entry 2 matched in commit " + sha)

    def test_hit_in_author_email(self):
        repo, sha = self.make_repo(author_email="zebra.quartz@example.invalid")
        status, out, err = self.run_local(repo, CANARY + "\nzebra.quartz@\n")
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in commit " + sha,
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertNotIn("zebra.quartz", out + err)

    def test_hit_in_committer_email(self):
        repo, sha = self.make_repo(committer_email="ember-gull@example.invalid")
        status, out, err = self.run_local(repo, CANARY + "\nember-gull@\n")
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in commit " + sha,
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertNotIn("ember-gull", out + err)

    def test_hit_in_branch_name(self):
        repo, _ = self.make_repo(branch="ember-gull-0042")
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 3 matched in branch", "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertNotIn("ember-gull-0042", out + err)

    def test_hit_in_file_path_withholds_path(self):
        repo, sha = self.make_repo({"zebra quartz notes.txt": "plain text\n"})
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in a file name (first seen in %s)" % sha[:12],
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertNotIn("notes.txt", out + err)

    def test_comments_and_blank_lines_ignored(self):
        text = "# a comment\n\n" + CANARY + "\n   \n# another\n" + ENTRY_A + "\n"
        self.assertEqual(barred_strings.parse_list(text), [CANARY, ENTRY_A])
        repo, sha = self.make_repo({"a.txt": "zebra quartz\n"})
        status, out, _ = self.run_local(repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out)[0], self.blob_line(repo, 2, "HEAD:a.txt", "a.txt", sha))

    # -- whitespace and invisible characters -------------------------------

    def test_whitespace_cannot_split_an_entry(self):
        entries = [barred_strings.fold("zebra quartz")]
        for text in ("zebra\nquartz", "zebra\r\nquartz", "zebra  quartz",
                     "zebra\tquartz", "zebra \n\t quartz", "zebra\u00a0quartz",
                     "zebra\u2003quartz"):
            with self.subTest(text=text):
                self.assertEqual(barred_strings.find_hits(text, entries), [1])
        # the entry side collapses too
        spaced = [barred_strings.fold("zebra   quartz")]
        self.assertEqual(barred_strings.find_hits("zebra quartz", spaced), [1])
        self.assertEqual(barred_strings.find_hits("zebra\nquartz", spaced), [1])

    def test_whitespace_collapse_keeps_word_flag(self):
        entries = [barred_strings.fold("zebra quartz")]
        self.assertEqual(
            barred_strings.find_hits("a zebra\nquartz b", entries, [True]), [1])
        self.assertEqual(
            barred_strings.find_hits("zebra\nquartzes", entries, [True]), [])
        self.assertEqual(
            barred_strings.find_hits("azebra\nquartz", entries, [True]), [])

    def test_whitespace_split_in_file_and_commit(self):
        repo, sha = self.make_repo({"a.txt": "zebra\nquartz\n"},
                                   message="zebra  quartz")
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            [self.blob_line(repo, 2, "HEAD:a.txt", "a.txt", sha),
             "entry 2 matched in commit " + sha,
             "barred-strings scan: 2 hit(s); failing"],
        )

    def test_tab_still_ends_an_entry(self):
        self.assertEqual(
            barred_strings.parse_list(CANARY + "\nzebra\tquartz\n"),
            [CANARY, "zebra"],
        )

    def test_invisible_format_characters_cannot_split_an_entry(self):
        entries = [barred_strings.fold("zebra quartz")]
        for name, mark in (("soft hyphen", "\u00ad"), ("zero-width space", "\u200b"),
                           ("zero-width joiner", "\u200d"), ("BOM", "\ufeff")):
            for text in ("zebr%sa quartz" % mark, "zebra quar%stz" % mark,
                         "zebra%s quartz" % mark):
                with self.subTest(mark=name, text=text):
                    self.assertEqual(barred_strings.find_hits(text, entries), [1])
            with self.subTest(mark=name, side="entry"):
                marked = [barred_strings.fold("zeb%sra quartz" % mark)]
                self.assertEqual(
                    barred_strings.find_hits("zebra quartz", marked), [1])

    def test_invisible_character_in_file_hits(self):
        repo, sha = self.make_repo({"a.txt": "zeb\u00adra quar\u200btz\n"})
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out)[0], self.blob_line(repo, 2, "HEAD:a.txt", "a.txt", sha))

    def test_entry_of_only_invisible_characters_fails(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_local(repo, CANARY + "\n\u200b\u00ad\n")
        self.assertEqual(status, 2)
        self.assertEqual(
            self.lines(err),
            ["barred-strings scan: entry 2 is empty after normalisation; "
             "failing closed"],
        )

    def test_list_with_leading_bom_scans_clean(self):
        repo, _ = self.make_repo()
        outside = os.path.join(self.tmp, "bom-list.txt")
        for body in (CANARY + "\n" + ENTRY_A + "\n",
                     "# header\n" + CANARY + "\n" + ENTRY_A + "\n"):
            with self.subTest(body=body[:8]):
                with open(outside, "wb") as handle:
                    handle.write(b"\xef\xbb\xbf" + body.encode("utf-8"))
                status, out, err = self.run_main(repo, {"BARRED_STRINGS_PATH": outside})
                self.assertEqual(status, 0)
                self.assertEqual(
                    self.lines(out),
                    ["barred-strings scan: clean (2 entries; 1 blobs; 1 paths; "
                     "1 commits; branch checked)"],
                )
                self.assertEqual(err, "")

    # -- list problems ----------------------------------------------------

    def test_canary_missing(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_local(repo, ENTRY_A + "\n" + CANARY + "\n")
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(self.lines(err), [MSG_NOT_CANARY])
        self.assertNotIn(ENTRY_A, out + err)

    def test_canary_too_short(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_local(repo, "barred-strings-canary-ab12\n" + ENTRY_A + "\n")
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_NOT_CANARY])

    def test_empty_secret(self):
        repo, _ = self.make_repo()
        for text in ("", "  \n\t\n"):
            status, out, err = self.run_local(repo, text)
            self.assertEqual(status, 2)
            self.assertEqual(self.lines(err), [MSG_NO_LIST])

    def test_comment_only_secret(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_local(repo, "# one\n# two\n")
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_NO_LIST])

    def test_missing_secret(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_main(repo, {})
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_NO_LIST])

    def test_matcher_misses_canary(self):
        repo, _ = self.make_repo()
        with mock.patch.object(barred_strings, "find_hits", return_value=[]):
            status, out, err = self.run_local(repo)
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_SELF_TEST])

    # -- CI mode ----------------------------------------------------------

    def write_event(self, head_repo):
        self.counter += 1
        path = os.path.join(self.tmp, "event%d.json" % self.counter)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pull_request": {"head": {"repo": head_repo}}}, handle)
        return path

    def ci_environ(self, event, **extra):
        environ = {
            "BARRED_STRINGS": LIST_TEXT,
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": event,
            "GITHUB_REPOSITORY": "example-org/example-repo",
        }
        environ.update(extra)
        return environ

    def test_fork_pull_request_fails(self):
        repo, _ = self.make_repo()
        for head in ({"full_name": "someone-else/example-repo"}, None):
            environ = self.ci_environ(
                "pull_request",
                GITHUB_EVENT_PATH=self.write_event(head),
                GITHUB_HEAD_REF="topic",
            )
            status, out, err = self.run_main(repo, environ)
            self.assertEqual(status, 2)
            self.assertEqual(self.lines(err), [MSG_FORK])
        # a fork gets the fork message even with no list at all
        environ = self.ci_environ(
            "pull_request",
            GITHUB_EVENT_PATH=self.write_event(None),
            BARRED_STRINGS="",
        )
        status, out, err = self.run_main(repo, environ)
        self.assertEqual((status, self.lines(err)), (2, [MSG_FORK]))

    def test_ci_branch_from_head_ref(self):
        repo, _ = self.make_repo()
        same = self.write_event({"full_name": "example-org/example-repo"})
        hit = ["barred-strings scan: 1 hit(s); failing"]
        clean = ["barred-strings scan: clean (3 entries; 1 blobs; 1 paths; "
                 "1 commits; branch checked)"]

        env = self.ci_environ("pull_request", GITHUB_EVENT_PATH=same,
                              GITHUB_HEAD_REF="ember-gull-0042",
                              GITHUB_REF_NAME="merge-ref")
        status, out, _ = self.run_main(repo, env)
        self.assertEqual((status, self.lines(out)), (1, hit))

        env = self.ci_environ("pull_request", GITHUB_EVENT_PATH=same,
                              GITHUB_HEAD_REF="topic",
                              GITHUB_REF_NAME="ember-gull-0042")
        status, out, _ = self.run_main(repo, env)
        self.assertEqual((status, self.lines(out)), (0, clean))

        env = self.ci_environ("push", GITHUB_HEAD_REF="ember-gull-0042",
                              GITHUB_REF_NAME="main")
        status, out, _ = self.run_main(repo, env)
        self.assertEqual((status, self.lines(out)), (0, clean))

        env = self.ci_environ("push", GITHUB_HEAD_REF="topic",
                              GITHUB_REF_NAME="ember-gull-0042")
        status, out, _ = self.run_main(repo, env)
        self.assertEqual((status, self.lines(out)), (1, hit))

    def assert_ci_output_has_count_only(self, repo, status, out, err, paths=()):
        self.assertEqual(status, 1)
        self.assertEqual(self.lines(out), ["barred-strings scan: 1 hit(s); failing"])
        self.assertEqual(err, "")
        shas = self.git(repo, "rev-list", "--all").split()
        shas += self.git(repo, "ls-tree", "-r", "HEAD").replace("\t", " ").split()
        short = [word[:7] for word in shas if len(word) >= 40]
        for fragment in ["entry ", "matched in"] + list(paths) + short:
            self.assertNotIn(fragment, out + err)

    def ci_push(self, ref="main", **extra):
        return self.ci_environ("push", GITHUB_REF_NAME=ref, **extra)

    def test_ci_hit_output_has_count_only_for_file_name(self):
        repo, _ = self.make_repo({"zebra quartz notes.txt": "plain text\n"})
        status, out, err = self.run_main(repo, self.ci_push())
        self.assert_ci_output_has_count_only(
            repo, status, out, err, paths=["zebra quartz notes.txt", "notes.txt"])

    def test_ci_hit_output_has_count_only_for_blob_text(self):
        repo, _ = self.make_repo({"docs/page.txt": "see zebra quartz here\n"})
        status, out, err = self.run_main(repo, self.ci_push())
        self.assert_ci_output_has_count_only(
            repo, status, out, err, paths=["docs/page.txt", "page.txt"])

    def test_ci_hit_output_has_count_only_for_commit(self):
        repo, _ = self.make_repo(message="notes: zebra quartz\n")
        status, out, err = self.run_main(repo, self.ci_push())
        self.assert_ci_output_has_count_only(repo, status, out, err)
        repo, _ = self.make_repo(author="zebra quartz bench")
        status, out, err = self.run_main(repo, self.ci_push())
        self.assert_ci_output_has_count_only(repo, status, out, err)

    def test_ci_hit_output_has_count_only_for_branch(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_main(repo, self.ci_push("ember-gull-0042"))
        self.assert_ci_output_has_count_only(
            repo, status, out, err, paths=["ember-gull-0042"])

    def multi_hit_repo(self):
        return self.make_repo({"a.txt": "zebra\nquartz\n"},
                              message="zebra  quartz", branch="ember-gull-0042")

    def test_ci_hit_output_has_count_only_for_several_hits(self):
        repo, _ = self.multi_hit_repo()
        status, out, err = self.run_main(repo, self.ci_push("ember-gull-0042"))
        self.assertEqual(status, 1)
        self.assertEqual(self.lines(out), ["barred-strings scan: 3 hit(s); failing"])
        self.assertEqual(err, "")

    def test_local_hit_output_keeps_entries(self):
        repo, _ = self.multi_hit_repo()
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        out_lines = self.lines(out)
        self.assertEqual(len(out_lines), 4)
        for line in out_lines[:3]:
            self.assertTrue(line.startswith("entry "), line)
        self.assertEqual(out_lines[3], "barred-strings scan: 3 hit(s); failing")
        self.assertEqual(err, "")

    def assert_ci_list_error_names_no_entry(self, list_text):
        repo, _ = self.make_repo()
        status, out, err = self.run_main(
            repo, self.ci_push(BARRED_STRINGS=list_text))
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_LIST_MALFORMED_CI])
        self.assertEqual(out, "")
        self.assertNotRegex(out + err, r"entry \d")

    def test_ci_empty_entry_names_no_entry(self):
        self.assert_ci_list_error_names_no_entry(CANARY + "\n\u200b\u00ad\n")

    def test_ci_not_canary_names_no_entry(self):
        self.assert_ci_list_error_names_no_entry(ENTRY_A + "\n" + CANARY + "\n")

    def test_ci_canary_flag_names_no_entry(self):
        self.assert_ci_list_error_names_no_entry(CANARY + "\tword\n" + ENTRY_A + "\n")

    def test_ci_empty_list_keeps_no_list_message(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_main(repo, self.ci_push(BARRED_STRINGS=""))
        self.assertEqual((status, self.lines(err)), (2, [MSG_NO_LIST]))

    def test_ci_refuses_list_file(self):
        repo, _ = self.make_repo()
        environ = self.ci_environ("push", GITHUB_REF_NAME="main",
                                  BARRED_STRINGS_PATH=os.path.join(self.tmp, "list.txt"))
        status, out, err = self.run_main(repo, environ)
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_FILE_IN_CI])

    def test_both_sources_refused(self):
        repo, _ = self.make_repo()
        environ = {"BARRED_STRINGS": LIST_TEXT,
                   "BARRED_STRINGS_PATH": os.path.join(self.tmp, "list.txt")}
        status, out, err = self.run_main(repo, environ)
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_BOTH])

    def test_list_file_inside_repo_refused(self):
        repo, _ = self.make_repo()
        inside = os.path.join(repo, "list.txt")
        with open(inside, "w", encoding="utf-8") as handle:
            handle.write(LIST_TEXT)
        status, out, err = self.run_main(repo, {"BARRED_STRINGS_PATH": inside})
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_FILE_IN_REPO])

    def test_list_file_outside_repo_works(self):
        repo, _ = self.make_repo()
        outside = os.path.join(self.tmp, "list.txt")
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write(LIST_TEXT)
        status, out, _ = self.run_main(repo, {"BARRED_STRINGS_PATH": outside})
        self.assertEqual(status, 0)

    def test_tab_note_never_matches(self):
        text = CANARY + "\n" + "zebra quartz\tember-gull\n"
        self.assertEqual(barred_strings.parse_list(text), [CANARY, "zebra quartz"])
        self.assertEqual(
            barred_strings.parse_list("barred-strings-canary-ab12cd34ef\tthe canary\n"),
            ["barred-strings-canary-ab12cd34ef"],
        )
        clean_repo, _ = self.make_repo({"a.txt": "ember-gull\n"})
        status, out, err = self.run_local(clean_repo, text)
        self.assertEqual(status, 0)
        self.assertEqual(
            self.lines(out),
            ["barred-strings scan: clean (2 entries; 1 blobs; 1 paths; "
             "1 commits; branch checked)"],
        )
        hit_repo, hit_sha = self.make_repo({"a.txt": "zebra quartz\n"})
        status, out2, err2 = self.run_local(hit_repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out2)[0],
            self.blob_line(hit_repo, 2, "HEAD:a.txt", "a.txt", hit_sha))
        status, out3, err3 = self.run_local(
            clean_repo, CANARY + "\tthe canary\n" + ENTRY_A + "\n"
        )
        self.assertEqual(status, 0)
        for note in ("the canary", "ember-gull"):
            for output in (out, err, out2, err2, out3, err3):
                self.assertNotIn(note, output)

    def test_empty_entry_before_tab_fails(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_local(repo, CANARY + "\n" + "\tonly a note\n")
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            self.lines(err),
            ["barred-strings scan: entry 2 is empty after normalisation; "
             "failing closed"],
        )
        self.assertNotIn("only a note", out + err)

    def test_non_utf8_commit_message_fails(self):
        repo = self.make_raw_commit_repo()
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            self.lines(err),
            ["barred-strings scan: commit %s is not UTF-8 text; failing closed"
             % self.raw_sha],
        )

    # -- repository states ------------------------------------------------

    def test_shallow_repo_fails(self):
        repo, _ = self.make_repo()
        self.commit(repo, "second commit")
        clone = os.path.join(self.tmp, "shallow")
        self.git(self.tmp, "clone", "-q", "--depth", "1", "file://" + repo, clone)
        status, out, err = self.run_local(clone)
        self.assertEqual(status, 2)
        self.assertEqual(self.lines(err), [MSG_SHALLOW])

    def test_non_utf8_file_fails(self):
        repo, first = self.make_repo({"data.bin": b"\xff\xfe\x00"})
        blob = self.git(repo, "rev-parse", "HEAD:data.bin")
        self.git(repo, "rm", "-q", "data.bin")
        self.commit(repo, "remove data.bin")
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            self.lines(err),
            ["barred-strings scan: blob %s (first seen in %s) is not UTF-8 text; "
             "failing closed" % (blob[:12], first[:12])],
        )

    def test_internal_error_hides_message(self):
        repo, _ = self.make_repo()
        with mock.patch.object(barred_strings, "scan_repo",
                               side_effect=RuntimeError(ENTRY_A)):
            status, out, err = self.run_local(repo)
        self.assertEqual(status, 2)
        self.assertEqual(
            self.lines(err),
            ["barred-strings scan: internal error (RuntimeError); failing closed"],
        )
        self.assertNotIn(ENTRY_A, out + err)

    # -- word flag --------------------------------------------------------

    def word_hits(self, text, flagged=True):
        entry = barred_strings.fold("quill")
        return barred_strings.find_hits(text, [entry], [flagged])

    def test_word_flag_hits_at_each_boundary(self):
        for text in ("quill", "quill box", "box quill", "a quill b", "a-quill-b",
                     "a_quill_b", "(quill)", "quill.", "x\nquill\ny", "x\tquill"):
            with self.subTest(text=text):
                self.assertEqual(self.word_hits(text), [1])

    def test_word_flag_no_hit_inside_word(self):
        for text in ("quills", "squill", "aquillb", "équill"):
            with self.subTest(text=text):
                self.assertEqual(self.word_hits(text), [])

    def test_word_flag_no_hit_next_to_digit(self):
        for text in ("quill2", "2quill", "quill\uff12"):
            with self.subTest(text=text):
                self.assertEqual(self.word_hits(text), [])

    def test_unflagged_entry_still_substring(self):
        for text in ("quills", "squill"):
            with self.subTest(text=text):
                self.assertEqual(self.word_hits(text, flagged=False), [1])

    def test_word_flag_is_case_insensitive(self):
        for flag in ("WORD", "Word", "word"):
            with self.subTest(flag=flag):
                pairs = barred_strings.parse_entries(CANARY + "\nquill\t" + flag + "\n")
                self.assertEqual(pairs, [(CANARY, False), ("quill", True)])
        self.assertEqual(self.word_hits("QUILL"), [1])

    def test_word_flag_with_leading_space_is_a_note(self):
        for field in (" word", "word ", "words"):
            with self.subTest(field=field):
                pairs = barred_strings.parse_entries(CANARY + "\nquill\t" + field + "\n")
                self.assertEqual(pairs, [(CANARY, False), ("quill", False)])
                flags = [flag for _, flag in pairs]
                self.assertEqual(
                    barred_strings.find_hits(
                        "quills", [barred_strings.fold(e) for e, _ in pairs], flags),
                    [2],
                )

    def test_word_flag_with_trailing_note(self):
        text = CANARY + "\nquill\tword\tshort entry\n"
        self.assertEqual(
            barred_strings.parse_entries(text), [(CANARY, False), ("quill", True)]
        )
        repo, _ = self.make_repo({"a.txt": "short entry\n"})
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 0)
        hit_repo, _ = self.make_repo({"a.txt": "see quill.\n"})
        status, out2, err2 = self.run_local(hit_repo, text)
        self.assertEqual(status, 1)
        for output in (out, err, out2, err2):
            self.assertNotIn("short entry", output)
            self.assertNotIn("quill", output)

    def test_word_flag_checks_every_occurrence(self):
        self.assertEqual(self.word_hits("quills and quill"), [1])
        self.assertEqual(self.word_hits("quills and squill"), [])

    def test_word_flag_applies_to_every_location(self):
        text = CANARY + "\nquill\tword\n"
        hit_line = "barred-strings scan: 1 hit(s); failing"
        repo, sha = self.make_repo({"a.txt": "see quill.\n"})
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            [self.blob_line(repo, 2, "HEAD:a.txt", "a.txt", sha), hit_line])
        repo, sha = self.make_repo({"quill notes.txt": "plain text\n"})
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in a file name (first seen in %s)" % sha[:12],
             hit_line]
        )
        repo, sha = self.make_repo(message="fix quill.")
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(self.lines(out), ["entry 2 matched in commit " + sha, hit_line])
        repo, _ = self.make_repo(branch="quill-fix")
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(self.lines(out), ["entry 2 matched in branch", hit_line])
        repo, _ = self.make_repo({"a.txt": "quills\n"})
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 0)
        self.assertEqual(
            self.lines(out),
            ["barred-strings scan: clean (2 entries; 1 blobs; 1 paths; "
             "1 commits; branch checked)"],
        )

    def test_word_flag_negative_at_every_location(self):
        text = CANARY + "\n" + "quill\tword\n"
        clean = ["barred-strings scan: clean (2 entries; 1 blobs; 1 paths; "
                 "1 commits; branch checked)"]
        repos = [
            self.make_repo({"quills.txt": "plain text\n"})[0],
            self.make_repo(message="fix quills")[0],
            self.make_repo(branch="quills-fix")[0],
        ]
        for repo in repos:
            with self.subTest(repo=os.path.basename(repo)):
                status, out, err = self.run_local(repo, text)
                self.assertEqual(status, 0)
                self.assertEqual(self.lines(out), clean)
                self.assertEqual(err, "")

    def test_file_self_test_fires_on_its_own(self):
        repo, _ = self.make_repo()
        real = barred_strings.find_hits

        def blind_without_flags(text, folded_entries, word_flags=None):
            if word_flags is None:
                return []
            return real(text, folded_entries, word_flags)

        with mock.patch.object(barred_strings, "find_hits",
                               side_effect=blind_without_flags):
            status, out, err = self.run_local(repo)
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(self.lines(err), [MSG_SELF_TEST])

    def test_canary_cannot_carry_word_flag(self):
        repo, _ = self.make_repo()
        status, out, err = self.run_local(repo, CANARY + "\tword\n" + ENTRY_A + "\n")
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(self.lines(err), [MSG_CANARY_FLAG])
        self.assertNotIn(CANARY, out + err)

    def test_word_self_test_detects_broken_boundary(self):
        repo, _ = self.make_repo()
        for value in (True, False):
            with self.subTest(always=value):
                with mock.patch.object(barred_strings, "is_boundary_char",
                                       return_value=value):
                    status, out, err = self.run_local(repo)
                self.assertEqual(status, 2)
                self.assertEqual(self.lines(err), [MSG_SELF_TEST])

    # -- history ----------------------------------------------------------

    def test_history_removed_word_still_fails(self):
        repo, first = self.make_repo({"notes.txt": "zebra quartz\n"})
        self.git(repo, "rm", "-q", "notes.txt")
        self.commit(repo, "remove notes")
        self.assertEqual(self.git(repo, "ls-tree", "-r", "HEAD"), "")
        blob = self.git(repo, "rev-parse", first + ":notes.txt")
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in blob %s (first seen at notes.txt in %s)"
             % (blob[:12], first[:12]),
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertEqual(err, "")

    def test_history_renamed_path_scanned(self):
        repo, first = self.make_repo({"zebra quartz.txt": "plain text\n"})
        self.git(repo, "mv", "zebra quartz.txt", "clean.txt")
        self.commit(repo, "rename the file")
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in a file name (first seen in %s)" % first[:12],
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertNotIn("quartz", out + err)

    def test_history_scan_positive_control(self):
        repo, _ = self.make_repo({"a.txt": "one\n"})
        self.write_file(repo, "a.txt", "two\n")
        self.git(repo, "add", "-A")
        self.commit(repo, "change a")
        self.git(repo, "rm", "-q", "a.txt")
        self.commit(repo, "delete a")
        commits = self.git(repo, "rev-list", "HEAD").split()
        self.assertEqual(len(commits), 3)
        blobs, paths = set(), set()
        for commit in commits:
            listing = self.git(repo, "ls-tree", "-r", "--full-tree", commit)
            for line in listing.splitlines():
                meta, path = line.split("\t", 1)
                blobs.add(meta.split(" ")[2])
                paths.add(path)
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 0)
        self.assertEqual(
            self.lines(out),
            ["barred-strings scan: clean (3 entries; %d blobs; %d paths; "
             "%d commits; branch checked)" % (len(blobs), len(paths), len(commits))],
        )
        self.assertEqual((len(blobs), len(paths)), (2, 1))

    def test_history_hit_line_format(self):
        repo, sha = self.make_repo({"a/b.txt": "x\n", "c.txt": "see ember-gull\n"})
        status, out, err = self.run_local(repo)
        blob = self.git(repo, "rev-parse", "HEAD:c.txt")
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 3 matched in blob %s (first seen at c.txt in %s)"
             % (blob[:12], sha[:12]),
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertEqual(len(blob[:12]), 12)

    def test_history_withholds_barred_path(self):
        repo, sha = self.make_repo({"ember-gull.txt": "see zebra quartz\n"})
        status, out, err = self.run_local(repo)
        blob = self.git(repo, "rev-parse", "HEAD:ember-gull.txt")
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in blob %s (first seen at a withheld path in %s)"
             % (blob[:12], sha[:12]),
             "entry 3 matched in a file name (first seen in %s)" % sha[:12],
             "barred-strings scan: 2 hit(s); failing"],
        )
        self.assertNotIn("ember-gull", out + err)
        self.assertNotIn(".txt", out + err)

    def test_history_each_blob_once(self):
        repo, first = self.make_repo({"one.txt": "zebra quartz\n"})
        self.write_file(repo, "two.txt", "zebra quartz\n")
        self.git(repo, "add", "-A")
        self.commit(repo, "copy to two")
        self.write_file(repo, "three.txt", "unrelated\n")
        self.git(repo, "add", "-A")
        self.commit(repo, "add three")
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        blob = self.git(repo, "rev-parse", "HEAD:one.txt")
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in blob %s (first seen at one.txt in %s)"
             % (blob[:12], first[:12]),
             "barred-strings scan: 1 hit(s); failing"],
        )

    def test_path_hit_names_first_seen_commit(self):
        repo, first = self.make_repo({"zebra quartz notes.txt": "plain text\n"})
        self.write_file(repo, "other.txt", "more plain text\n")
        self.git(repo, "add", "-A")
        second = self.commit(repo, "add other")
        self.assertNotEqual(first[:12], second[:12])
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in a file name (first seen in %s)" % first[:12],
             "barred-strings scan: 1 hit(s); failing"],
        )
        self.assertEqual(len(first[:12]), 12)
        self.assertNotIn(second[:12], out + err)
        self.assertEqual(err, "")

    def test_submodule_entry_fails_closed(self):
        repo, _ = self.make_repo()
        self.git(repo, "update-index", "--add", "--cacheinfo",
                 "160000,%s,vendor/sub" % ("ab" * 20))
        second = self.commit(repo, "add a submodule entry")
        self.assertEqual(
            self.git(repo, "ls-tree", "HEAD", "vendor/sub").split(" ")[0], "160000")
        status, out, err = self.run_local(repo)
        self.assertEqual(status, 2)
        self.assertNotIn("clean", out + err)
        self.assertEqual(out, "")
        self.assertEqual(
            self.lines(err),
            ["barred-strings scan: a submodule entry first seen in %s; "
             "failing closed" % second[:12]],
        )

    def test_hits_print_in_integer_entry_order(self):
        entries = ["alpha-two"] + ["filler-%d" % n for n in range(3, 10)] + [
            "beta-ten", "filler-11"]
        text = CANARY + "\n" + "\n".join(entries) + "\n"
        self.assertEqual(len(barred_strings.parse_list(text)), 11)
        self.assertEqual(entries[0], "alpha-two")
        self.assertEqual(entries[8], "beta-ten")
        # beta-ten is entry 10, alpha-two is entry 2
        repo, sha = self.make_repo(
            {"a.txt": "beta-ten and alpha-two\n"},
            message="note: beta-ten and alpha-two\n")
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            [self.blob_line(repo, 2, "HEAD:a.txt", "a.txt", sha),
             self.blob_line(repo, 10, "HEAD:a.txt", "a.txt", sha),
             "entry 2 matched in commit " + sha,
             "entry 10 matched in commit " + sha,
             "barred-strings scan: 4 hit(s); failing"],
        )
        repo, sha = self.make_repo({"beta-ten alpha-two.txt": "plain text\n"})
        status, out, err = self.run_local(repo, text)
        self.assertEqual(status, 1)
        self.assertEqual(
            self.lines(out),
            ["entry 2 matched in a file name (first seen in %s)" % sha[:12],
             "entry 10 matched in a file name (first seen in %s)" % sha[:12],
             "barred-strings scan: 2 hit(s); failing"],
        )

    # -- output discipline ------------------------------------------------

    def exercise_every_path(self):
        """Run each hit kind and each exit-2 path that involves entries."""
        files = self.make_repo({"zebra quartz.txt": "ember-gull and zebra quartz\n"},
                               branch="ember-gull-0042",
                               message="note: zebra quartz\n",
                               author="zebra quartz bench")[0]
        self.run_local(files)
        repo, _ = self.make_repo()
        self.run_local(repo, ENTRY_A + "\n" + CANARY + "\n")
        self.run_local(repo, "barred-strings-canary-ab12\n" + ENTRY_A + "\n")
        with mock.patch.object(barred_strings, "find_hits", return_value=[]):
            self.run_local(repo)
        with mock.patch.object(barred_strings, "scan_repo",
                               side_effect=RuntimeError(ENTRY_A)):
            self.run_local(repo)
        bad, _ = self.make_repo({"data.bin": b"\xff\xfe\x00"})
        self.run_local(bad)
        self.run_main(repo, {"BARRED_STRINGS": LIST_TEXT, "BARRED_STRINGS_PATH": "x"})
        self.run_local(repo, CANARY + "\n\tonly a note\n")
        self.run_local(
            files, CANARY + "\tthe canary\n" + ENTRY_A + "\tember-gull\n"
        )
        self.run_local(self.make_raw_commit_repo(), LIST_TEXT)
        word_list = CANARY + "\n" + "quill\tword\tshort entry\n"
        word_repo, _ = self.make_repo({"quill.txt": "see quill.\n"},
                                      branch="quill-fix", message="fix quill.\n")
        self.run_local(word_repo, word_list)
        self.run_local(repo, CANARY + "\tword\n" + ENTRY_A + "\n")

    def test_output_never_contains_term(self):
        self.exercise_every_path()
        self.assertGreaterEqual(len(self.outputs), 10)
        entries = [CANARY, ENTRY_A, ENTRY_B, "ember-gull-0042",
                   "only a note", "the canary", "ember-gull", "quill",
                   "short entry"]
        for out, err in self.outputs:
            # the fixed self-test and canary-flag messages contain "the canary"
            combined = (out + err).replace(MSG_SELF_TEST, "").replace(
                MSG_CANARY_FLAG, "")
            for entry in entries:
                self.assertNotIn(entry, combined)
                self.assertNotIn(barred_strings.fold(entry), barred_strings.fold(combined))

    def test_no_annotations_or_summary(self):
        self.exercise_every_path()
        for out, err in self.outputs:
            for line in (out + err).splitlines():
                self.assertFalse(line.startswith("::"), line)
        with open(barred_strings.__file__, encoding="utf-8") as handle:
            source = handle.read()
        for banned in ("GITHUB_STEP_SUMMARY", "::error", "::warning",
                       "::notice", "add-mask"):
            self.assertNotIn(banned, source)

    def test_env_keys_are_closed(self):
        self.assertEqual(
            barred_strings.ENV_KEYS,
            ("BARRED_STRINGS", "BARRED_STRINGS_PATH", "GITHUB_ACTIONS",
             "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH", "GITHUB_REPOSITORY",
             "GITHUB_HEAD_REF", "GITHUB_REF_NAME"),
        )
        with open(barred_strings.__file__, encoding="utf-8") as handle:
            source = handle.read()
        keys = []
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "environ"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                keys.append(node.args[0].value)
            if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                    and node.value.id == "environ"
                    and isinstance(node.slice, ast.Constant)):
                keys.append(node.slice.value)
        self.assertTrue(keys)
        for key in keys:
            self.assertIn(key, barred_strings.ENV_KEYS)
        self.assertEqual(source.count("os.environ"), 1)
        self.assertEqual(source.count("getenv"), 0)


if __name__ == "__main__":
    unittest.main()
