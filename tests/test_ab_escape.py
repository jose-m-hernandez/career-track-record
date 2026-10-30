"""Tests that Reader A/B escapes what it prints (career_track_record.ab, cli).

Everything the tool prints, or writes into a result file, that comes from an argument, a file
name or a file's contents goes through the one function ``barred.printed_path`` is: a
backslash, a line break, a tab, a control character, a format character or U+2028/U+2029
is printed as an escape. These tests put a line break and the zero-width space U+200B (written
as an escape in this source) into each surface and check that the escaped form is printed and
that nothing splits a line. Where a surface cannot hold a line feed (a plan line, a line of a
file that is split at line feeds) a vertical tab or U+2028 stands in: ``str.splitlines`` splits
at those too, so a raw one would show as an extra line.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import ab  # noqa: E402
from tests.test_ab import PREFER_GLANCE, Setup, sha256_of  # noqa: E402
from tests.test_ab_run_failures import one_line  # noqa: E402
from tests.test_cli import track  # noqa: E402

ZWSP = "\u200b"


class EscapeCase(unittest.TestCase):
    def test_the_escaping_function_is_the_one_barred_prints_paths_with(self):
        from career_track_record import barred
        self.assertIs(ab._show, barred.printed_path)
        self.assertEqual(ab._show("a\nb" + ZWSP + "\\"), "a\\nb\\u200b\\\\")

    def test_a_run_folder_error_line_is_escaped(self):
        error = ab.RunFolderError("write", "a\nb" + ZWSP, "c\nd")
        self.assertEqual(error.line, "cannot write a\\nb\\u200b: c\\nd")

    def test_a_plan_path_in_the_command(self):
        # A path with a line feed and U+200B, named on the command line.
        tmp = Setup(self).folder
        code, out, err = track("ab", "freeze", os.path.join(tmp, "no\nsuch" + ZWSP))
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err),
                         "cannot run: cannot read the plan: no\\nsuch\\u200b")

    # Known limit: a plan file whose own name holds a line break can be frozen but not run
    # (the freeze file lists names one to a line). The freeze is what this test shows.
    def test_a_plan_path_that_exists(self):
        s = Setup(self)
        weird = s.path("pl\nan" + ZWSP + ".txt")
        os.rename(s.plan_path, weird)
        result = ab.freeze(weird)
        self.assertEqual((result.exit_code, result.text),
                         (0, "freeze written: pl\\nan\\u200b.txt.freeze\n"))
        self.assertEqual(ab.score(os.path.join(s.folder, "gone\n" + ZWSP)).error,
                         "no freeze file: gone\\n\\u200b.freeze")
        # A plan with no freeze of its own: the freeze file it lacks is named, escaped.
        other = s.path("o\nther" + ZWSP + ".txt")
        with open(weird, "rb") as source, open(other, "wb") as target:
            target.write(source.read())
        refused = ab.run(other)
        self.assertEqual(refused.error.splitlines(),
                         ["no freeze file: o\\nther\\u200b.txt.freeze"])
        self.assertEqual(len(refused.error.split("\n")), 1)

    def test_version_and_posting_file_names(self):
        s = Setup(self, posting="post\x0bing" + ZWSP + ".txt",
                  versions=["base | base.txt", "skills-top | skills\u2028-top" + ZWSP + ".txt",
                            "skills-top-short | skills-top-short.txt"])
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.split("\n"), [
            "missing input: post\\x0bing\\u200b.txt",
            "missing input: skills\\u2028-top\\u200b.txt"])
        self.assertEqual(len(result.error.splitlines()), 2)

    def test_a_changed_version_file_name_after_the_freeze(self):
        name = "skills\u2028-top" + ZWSP + ".txt"
        s = Setup(self, versions=["base | base.txt", "skills-top | " + name,
                                  "skills-top-short | skills-top-short.txt"])
        os.rename(s.path("skills-top.txt"), s.path(name))
        self.assertEqual(s.freeze().exit_code, 0)
        s.edit(name, lambda text: text + "  \n")
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.splitlines(),
                         ["changed since the freeze: skills\\u2028-top\\u200b.txt"])

    def test_changed_lines_of_the_isolation_check(self):
        s = Setup(self)
        text = s.read("skills-top.txt")
        old = next(line for line in text.split("\n") if "ninety" in line)
        new = old.replace("ninety", "nine\x0bty" + ZWSP + "\u2028x")
        s.write("skills-top.txt", text.replace(old, new))
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual(result.exit_code, 2)
        shown = ab.collapsed_lines(old)[0], ab.collapsed_lines(new)[0].replace(
            "\x0b", "\\x0b").replace(ZWSP, "\\u200b").replace("\u2028", "\\u2028")
        self.assertEqual(result.error.splitlines(), [
            "c1: changed line outside the change scope: - " + shown[0],
            "c1: changed line outside the change scope: + " + shown[1]])
        self.assertIn("nine\\x0bty\\u200b\\u2028x", shown[1])
        self.assertEqual(len(result.error.split("\n")), 2)

    def test_the_command_in_the_live_preview(self):
        s = Setup(self, readers=["r1 | fake", "r2 | tool\x0b--flag" + ZWSP + "\u2028end"])
        self.assertEqual(s.freeze().exit_code, 0)
        result = s.run()
        self.assertEqual((result.exit_code, result.error), (0, ""))
        self.assertIn("reader r2: tool\\x0b--flag\\u200b\\u2028end (cost 1 per read)",
                      result.text.splitlines())
        self.assertEqual(len(result.text.splitlines()), len(result.text.split("\n")) - 1)
        self.assertNotIn("\x0b", result.text)
        self.assertNotIn(ZWSP, result.text)

    def test_reply_field_text_in_a_result_row(self):
        s = Setup(self, fake_reader=[PREFER_GLANCE])
        self.assertEqual(s.frozen_run().exit_code, 0)
        before = s.result_lines()
        with open(os.path.join(s.read_folder("c1", 1), ab.READ_REPLY), "w",
                  encoding="utf-8") as handle:
            handle.write("READ: c1/1\nPRIOR: a former\ncolleague" + ZWSP + "\nSCORE-A: 3\n"
                         "SCORE-B: 9\nPREFER: A, strongly\n")
        result = s.score()
        self.assertEqual(result.exit_code, 0)
        row = ("read c1/1: reader=r1 A=base B=skills-top scores=3/9 prefer=A, strongly "
               "flags=PRIOR is not nothing: a former\\ncolleague\\u200b")
        self.assertIn(row, result.text.splitlines())
        self.assertEqual(s.read("result-2.txt"), result.text)
        self.assertEqual(len(result.text.splitlines()), len(before))
        self.assertEqual(len([x for x in result.text.splitlines() if "colleague" in x]), 1)

    def test_a_failure_reason_from_the_run_log(self):
        s = Setup(self, fake_reader=[PREFER_GLANCE])
        self.assertEqual(s.frozen_run().exit_code, 0)
        s.edit(ab.RUN_LOG, lambda text: text + "failure c1/1: exit\u2028status" + ZWSP + "\n")
        result = s.score()
        self.assertEqual(result.exit_code, 1)
        lines = result.text.splitlines()
        self.assertIn("failed read c1/1: exit\\u2028status\\u200b", lines)
        self.assertIn("read c1/1: reader=r1 A=base B=skills-top FAILED "
                      "(exit\\u2028status\\u200b)", lines)
        self.assertEqual(result.error.splitlines()[0], "failed read c1/1: exit\\u2028status\\u200b")
        self.assertEqual(len(result.text.split("\n")) - 1, len(lines))

    def test_a_mechanism_name(self):
        s = Setup(self, mechanisms=["a\x0bb" + ZWSP + " | default | supported at 1 or more"])
        self.assertEqual(s.frozen_run().exit_code, 0)
        lines = s.result_lines()
        self.assertIn("mechanism a\\x0bb\\u200b in c1 count: 0 of 6 valid reads", lines)
        self.assertEqual(len(s.read("result-1.txt").split("\n")) - 1,
                         len(s.read("result-1.txt").splitlines()))

    def test_a_row_of_the_key(self):
        s = Setup(self)
        self.assertEqual(s.frozen_run().exit_code, 0)
        s.edit(ab.KEY_FILE, lambda text: text.replace("aa/1\tr1\t", "aa/1\tr" + ZWSP + "1\t", 1))
        digest = sha256_of(s.path(ab.KEY_FILE))
        s.edit(ab.RUN_LOG, lambda text: "".join(
            ("key sha256: %s\n" % digest) if line.startswith("key sha256: ") else line + "\n"
            for line in text.splitlines()))
        result = s.score()
        self.assertEqual(result.exit_code, 0, result.error)
        self.assertIn("key aa/1: reader=r\\u200b1 A=skills-top B=skills-top",
                      result.text.splitlines())
        self.assertIn("read aa/1: reader=r\\u200b1 A=skills-top B=skills-top scores=5/5 "
                      "prefer=TIE flags=none", result.text.splitlines())

    def test_values_in_plan_messages(self):
        s = Setup(self, **{"colo" + ZWSP + "r": "blue"})
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("plan line %d: unknown key colo\\u200br" % s.line_of("colo"),
                      result.error.splitlines())
        t = Setup(self, change_scope=["(\x0b" + ZWSP])
        self.assertIn("plan line %d: not a valid pattern: (\\x0b\\u200b" % t.line_of("("),
                      t.freeze().error.splitlines())
        self.assertEqual(len(t.freeze().error.split("\n")), 1)

    def test_names_of_files_in_the_run_folder(self):
        s = Setup(self)
        with open(s.path("x\ny" + ZWSP + ".freeze"), "w", encoding="utf-8") as handle:
            handle.write("")
        os.makedirs(s.path(ab.READS_DIR, "aa", "1\n" + ZWSP))
        with open(s.path(ab.READS_DIR, "aa", "1\n" + ZWSP, ab.READ_REPLY), "w") as handle:
            handle.write("")
        result = s.freeze()
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.error.split("\n"), [
            "a freeze file already exists: x\\ny\\u200b.freeze",
            "the run folder already holds a reply: reads/aa/1\\n\\u200b/REPLY.txt"])

    def test_names_in_the_command_line_errors(self):
        code, out, err = track("ab", "bo\ngus" + ZWSP)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err),
                         "cannot run: unknown ab subcommand bo\\ngus\\u200b")
        code, out, err = track("ab", "freeze", "--o\np" + ZWSP, "plan.txt")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err), "cannot run: unknown option --o\\np\\u200b")
        code, out, err = track("ab", "--x\ty" + ZWSP + "=1")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(one_line(self, err), "cannot run: unknown option --x\\ty\\u200b")


if __name__ == "__main__":
    unittest.main()
