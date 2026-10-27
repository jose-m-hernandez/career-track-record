"""Tests for the track-record command line. All data here is invented."""

import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import posting_file  # noqa: E402

K = os.path.join("tests", "fixtures", "keywords")
T1 = os.path.join(K, "terms-t1.tsv")

TABLE_11_1 = (
    "| family | postings | % | hits | top variants |\n"
    "|---|---|---|---|---|\n"
    "| agents | 3/3 | 100% | 3 | `agents` (3) |\n"
    "| evals | 2/3 | 67% | 2 | `evals` (2) |\n"
    "| python | 2/3 | 67% | 2 | `python` (2) |\n"
    "| field-notes | 1/3 | 33% | 1 | `field notes` (1) |\n"
    "| knowledge-graph | 1/3 | 33% | 1 | `knowledge graph` (1) |\n"
)
REPORT_11_4 = (
    "| family | demand | copy.txt | gap |\n"
    "|---|---|---|---|\n"
    "| agents | 3/3 (100%) | 1 |  |\n"
    "| evals | 2/3 (67%) | 1 |  |\n"
    "| python | 2/3 (67%) | 0 | GAP |\n"
    "| field-notes (chosen) | 1/3 (33%) | 0 | GAP |\n"
    "| knowledge-graph | 1/3 (33%) | 0 | GAP |\n"
    "\n"
    "Keywords: python (67% of postings, 0 in copy); field-notes (33% of postings, 0 in copy); "
    "knowledge-graph (33% of postings, 0 in copy)\n"
)


def track(*args):
    env = dict(os.environ, PYTHONPATH="src", PYTHONDONTWRITEBYTECODE="1")
    with open(os.devnull, "rb") as devnull:
        proc = subprocess.run(
            [sys.executable, "-m", "career_track_record"] + list(args),
            cwd=ROOT, env=env, stdin=devnull, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


class CliBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)

    def assertCannotRun(self, args, *needles):
        code, out, err = track(*args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(err.count("\n"), 1, err)
        self.assertTrue(err.endswith("\n"))
        for needle in needles:
            self.assertIn(needle, err)
        return err


class DemandCli(CliBase):
    def test_11_1_shape(self):
        code, out, err = track("keywords", "demand", "--postings",
                               os.path.join(K, "postings-p1"), "--terms", T1)
        self.assertEqual((code, err), (0, ""))
        heading, blank, rest = out.split("\n", 2)
        self.assertRegex(heading, r"^# Demand, \d{4}-\d{2}-\d{2} \(3 postings\)$")
        self.assertEqual(blank, "")
        self.assertEqual(rest, TABLE_11_1 + "\n")

    def test_out_file_has_one_final_line_feed(self):
        target = self.path("demand.md")
        code, out, err = track("keywords", "demand", "--postings",
                               os.path.join(K, "postings-p1"), "--terms", T1,
                               "--out", target)
        self.assertEqual((code, err), (0, ""))
        with open(target, "rb") as handle:
            written = handle.read().decode("utf-8")
        self.assertEqual(written, out[:-1])
        self.assertTrue(written.endswith("|\n"))
        self.assertFalse(written.endswith("\n\n"))
        self.assertTrue(out.endswith("|\n\n"))

    def test_out_is_not_written_when_it_cannot_run(self):
        target = self.path("demand.md")
        empty = self.path("empty")
        os.makedirs(empty)
        self.assertCannotRun(["keywords", "demand", "--postings", empty, "--terms", T1,
                              "--out", target])
        self.assertFalse(os.path.exists(target))


class CoverageCli(CliBase):
    def test_11_2(self):
        code, out, err = track("keywords", "coverage", "--terms", T1,
                               os.path.join(K, "copy.txt"), os.path.join(K, "copy2.ts"))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, (
            "| family | copy.txt | copy2.ts |\n"
            "|---|---|---|\n"
            "| agents | 1 | 0 |\n"
            "| evals | 1 | 0 |\n"
            "| python | 0 | 1 |\n"
            "| knowledge-graph | 0 | 0 |\n"
            "| field-notes | 0 | 0 |\n"))

    def test_11_3_keep_notes(self):
        code, out, err = track("keywords", "coverage", "--terms", T1, "--keep-notes",
                               os.path.join(K, "copy2.ts"))
        self.assertEqual((code, err), (0, ""))
        rows = [line.split(" | ") for line in out.strip().split("\n")[2:]]
        got = {r[0].lstrip("| "): r[1].rstrip(" |") for r in rows}
        self.assertEqual(got, {"agents": "0", "evals": "0", "python": "2",
                               "knowledge-graph": "1", "field-notes": "1"})

    def test_case_6_missing_copy(self):
        self.assertCannotRun(["keywords", "coverage", "--terms", T1,
                              os.path.join(K, "copy.txt"), self.path("missing.txt")],
                             "missing.txt")

    def test_collision_suffix_on_the_command_line(self):
        for sub in ("one", "two"):
            os.makedirs(self.path(sub))
            with open(self.path(sub, "x.txt"), "w", encoding="utf-8") as handle:
                handle.write("I build agents.\n")
        code, out, err = track("keywords", "coverage", "--terms", T1,
                               self.path("one", "x.txt"), self.path("two", "x.txt"))
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("| family | one/x.txt | two/x.txt |\n"), out)


class ReportCli(CliBase):
    def test_11_4(self):
        code, out, err = track("keywords", "report", "--postings",
                               os.path.join(K, "postings-p1"), "--terms", T1,
                               "--copy", os.path.join(K, "copy.txt"))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, REPORT_11_4)

    def test_11_5(self):
        code, out, err = track("keywords", "report", "--postings",
                               os.path.join(K, "postings-p1"), "--terms", T1,
                               "--copy", os.path.join(K, "copy.txt"),
                               os.path.join(K, "copy2.ts"))
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.endswith(
            "Keywords: field-notes (33% of postings, 0 in copy); "
            "knowledge-graph (33% of postings, 0 in copy)\n"))

    def test_11_6_edges(self):
        for folder, summary in (("postings-e10", "Keywords: python (30% of postings, 0 in copy)"),
                                ("postings-e7", "Keywords: none"),
                                ("postings-e8", "Keywords: none")):
            code, out, err = track("keywords", "report", "--postings",
                                   os.path.join(K, folder), "--terms", T1,
                                   "--copy", os.path.join(K, "copy4.txt"))
            self.assertEqual((code, err), (0, ""), folder)
            self.assertTrue(out.endswith("\n\n" + summary + "\n"), (folder, out))

    def test_11_9(self):
        code, out, err = track("keywords", "report", "--postings",
                               os.path.join(K, "postings-p1-ab"), "--terms", T1,
                               "--copy", os.path.join(K, "copy3.txt"))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("| field-notes (chosen) | 0/2 (0%) | 1 |  |\n", out)
        summary = out.strip().split("\n")[-1]
        self.assertIn("python", summary)
        self.assertNotIn("field-notes", summary)

    def test_keep_notes_flag(self):
        code, out, err = track("keywords", "report", "--postings",
                               os.path.join(K, "postings-p1"), "--terms", T1,
                               "--keep-notes", "--copy", os.path.join(K, "copy2.ts"))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("| python | 2/3 (67%) | 2 |  |\n", out)


class CannotRunCli(CliBase):
    def terms_args(self):
        return ["--terms", T1]

    def test_case_1_empty_folder(self):
        empty = self.path("empty")
        os.makedirs(empty)
        self.assertCannotRun(["keywords", "demand", "--postings", empty] + self.terms_args(),
                             ".txt")
        self.assertCannotRun(["keywords", "report", "--postings", empty, "--terms", T1,
                              "--copy", os.path.join(K, "copy.txt")], ".txt")

    def test_case_2_wrong_key(self):
        folder = self.path("p")
        os.makedirs(folder)
        with open(os.path.join(K, "postings-p1", "2026-01-15-example-b.txt"),
                  encoding="utf-8") as handle:
            text = handle.read()
        with open(os.path.join(folder, "b.txt"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.replace("http_status", "status"))
        self.assertCannotRun(["keywords", "demand", "--postings", folder, "--terms", T1],
                             "header")

    def test_case_3_hash_fails(self):
        folder = self.path("p")
        os.makedirs(folder)
        with open(os.path.join(K, "postings-p1", "2026-01-15-example-a.txt"),
                  encoding="utf-8") as handle:
            text = handle.read()
        with open(os.path.join(folder, "a.txt"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.replace("a plus.", "a must."))
        self.assertCannotRun(["keywords", "report", "--postings", folder, "--terms", T1,
                              "--copy", os.path.join(K, "copy.txt")], "sha256")

    def test_case_4_must_find_has_zero_demand(self):
        err = self.assertCannotRun(["keywords", "report", "--postings",
                                    os.path.join(K, "postings-d"), "--terms", T1,
                                    "--copy", os.path.join(K, "copy.txt")], "must-find")
        self.assertNotIn("Traceback", err)
        self.assertCannotRun(["keywords", "demand", "--postings",
                              os.path.join(K, "postings-d"), "--terms", T1], "must-find")

    def test_case_4_no_must_find_family(self):
        terms = self.path("terms.tsv")
        with open(terms, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("family\tpattern\tnote\nagents\tagents\t\n")
        self.assertCannotRun(["keywords", "demand", "--postings",
                              os.path.join(K, "postings-p1"), "--terms", terms], "must-find")

    def test_case_5_missing_terms(self):
        missing = self.path("none.tsv")
        self.assertCannotRun(["keywords", "demand", "--postings",
                              os.path.join(K, "postings-p1"), "--terms", missing], "none.tsv")
        self.assertCannotRun(["keywords", "coverage", "--terms", missing,
                              os.path.join(K, "copy.txt")], "none.tsv")

    def test_case_5_header_only_terms(self):
        terms = self.path("terms.tsv")
        with open(terms, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("family\tpattern\tnote\n")
        self.assertCannotRun(["keywords", "coverage", "--terms", terms,
                              os.path.join(K, "copy.txt")], "term table")

    def test_case_6_copy_missing(self):
        self.assertCannotRun(["keywords", "report", "--postings",
                              os.path.join(K, "postings-p1"), "--terms", T1,
                              "--copy", self.path("missing.txt")], "missing.txt")

    def test_case_8_invalid_utf8(self):
        bad = self.path("bad.bin")
        with open(bad, "wb") as handle:
            handle.write(b"agents \xff\n")
        self.assertCannotRun(["keywords", "coverage", "--terms", T1, bad], "UTF-8")
        self.assertCannotRun(["keywords", "coverage", "--terms", bad,
                              os.path.join(K, "copy.txt")], "UTF-8")
        folder = self.path("p")
        os.makedirs(folder)
        with open(os.path.join(folder, "a.txt"), "wb") as handle:
            handle.write(b"\xff\xfe")
        self.assertCannotRun(["keywords", "demand", "--postings", folder, "--terms", T1],
                             "UTF-8")

    def test_case_9_invalid_pattern(self):
        terms = self.path("terms.tsv")
        with open(terms, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("family\tpattern\tnote\nagents\t(oops\tmust-find\n")
        self.assertCannotRun(["keywords", "coverage", "--terms", terms,
                              os.path.join(K, "copy.txt")], "(oops")

    def test_usage_errors_keep_argparse_exit_2(self):
        for args in ([], ["keywords"], ["keywords", "demand"],
                     ["keywords", "report", "--postings", "x", "--terms", T1],
                     ["keywords", "coverage", "--terms", T1]):
            code, out, err = track(*args)
            self.assertEqual(code, 2, args)
            self.assertEqual(out, "")
            self.assertIn("usage:", err)

    def test_no_traceback_is_ever_shown(self):
        code, out, err = track("keywords", "coverage", "--terms", T1, self.path("zz"))
        self.assertNotIn("Traceback", err)


class TopLevelHelpListsToolsCli(CliBase):
    def test_top_level_help_lists_barred_and_tone(self):
        code, out, err = track("--help")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        for line in (
                "    barred    report wording from your own barred list",
                "    tone      flag hype, hedges and filler in your copy"):
            with self.subTest(line=line):
                self.assertIn(line, lines)


if __name__ == "__main__":
    unittest.main()
