"""Gate: docs/provenance.md has exactly one row per file in the repository.

The ledger has four columns (path, harness, model, date). This test fails if a file has no
row, a row has no file, a path appears twice, rows are out of order, or a row breaks the
format rules written in the ledger header."""

import datetime
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "docs", "provenance.md")
PARAGRAPH = (
    "This ledger lists every file in the repository once, with the harness "
    "and model recorded writing to it and the day (UTC) of the latest "
    "recorded write. A filled row names every harness and model that the "
    "maintainer's local session records show writing to the file. It does "
    "not say who created the file, or that nothing else wrote to it. `not "
    "recorded` means those records hold no write to the file; most files "
    "written before 2026-11-01 have none. A change that adds or edits a "
    "file updates that file's row in the same change. "
    "`tests/test_provenance.py` fails if a file has no row, a row has no "
    "file, or the table has any column other than these four. The ledger "
    "lists itself."
)
HEADER = "| path | harness | model | date |"
SEPARATOR = "| --- | --- | --- | --- |"
NOT_RECORDED = "not recorded"
VALUE = re.compile(r"[a-z0-9][a-z0-9.-]*\Z")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def repository_files():
    """Return the file list from git, or fail the test if git cannot run."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise AssertionError("git ls-files could not run: %s" % type(error).__name__)
    return [p for p in proc.stdout.decode("utf-8").split("\0") if p]


def read_head():
    """Return the ledger header text the ledger must start with, as lines."""
    with open(LEDGER, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    return lines


def problems(text, files):
    """Return a list of messages naming each way `text` fails as a ledger for `files`."""
    found = []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    else:
        found.append("the ledger does not end with a single newline")
    try:
        start = lines.index(HEADER)
    except ValueError:
        return found + ["header row is not exactly: %s" % HEADER]
    if lines[start + 1 : start + 2] != [SEPARATOR]:
        return found + ["separator row is not exactly: %s" % SEPARATOR]
    rows = []
    for number, line in enumerate(lines[start + 2 :], start + 3):
        cells = line.split(" | ")
        if not (line.startswith("| ") and line.endswith(" |")) or len(cells) != 4:
            found.append("line %d is not a row with exactly four cells" % number)
            continue
        cells[0] = cells[0][2:]
        cells[3] = cells[3][:-2]
        rows.append((number, cells))
    seen = {}
    for number, (path, harness, model, day) in rows:
        if "|" in path or "\\" in path or path != path.strip():
            found.append("line %d: path has a forbidden character or space" % number)
        if path in seen:
            found.append("line %d: path appears twice: %s" % (number, path))
        seen[path] = number
        cells = (harness, model, day)
        blanks = [c == NOT_RECORDED for c in cells]
        if any(blanks) and not all(blanks):
            found.append("line %d: %s is partly filled" % (number, path))
        elif not any(blanks):
            for name, value in (("harness", harness), ("model", model)):
                parts = value.split(", ")
                if parts != sorted(set(parts)) or not all(VALUE.match(p) for p in parts):
                    found.append("line %d: %s has a bad %s" % (number, path, name))
            try:
                if not DAY.match(day):
                    raise ValueError(day)
                datetime.date(int(day[:4]), int(day[5:7]), int(day[8:]))
            except ValueError:
                found.append("line %d: %s has a bad date" % (number, path))
    paths = [r[1][0] for r in rows]
    if paths != sorted(paths):
        found.append("rows are not in ascending order of path")
    for path in sorted(set(paths) - set(files)):
        found.append("row has no file: %s" % path)
    for path in sorted(set(files) - set(paths)):
        found.append("file has no row: %s" % path)
    return found


def small(*rows):
    head = "# t\n\n" + HEADER + "\n" + SEPARATOR + "\n"
    return head + "".join(r + "\n" for r in rows)


GOOD_A = "| a.txt | claude-code | claude-sonnet-5-5 | 2026-11-01 |"
GOOD_B = "| b.txt | not recorded | not recorded | not recorded |"


class ProvenanceCase(unittest.TestCase):
    def test_ledger_header_is_the_ruled_text(self):
        lines = read_head()
        self.assertEqual(lines[:5], ["# Provenance", "", PARAGRAPH, "", HEADER])
        self.assertEqual(lines[5], SEPARATOR)

    def test_every_file_has_one_row_and_every_row_a_file(self):
        with open(LEDGER, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(problems(text, repository_files()), [])

    def test_a_correct_small_ledger_passes(self):
        self.assertEqual(problems(small(GOOD_A, GOOD_B), ["a.txt", "b.txt"]), [])

    def test_a_missing_row_is_refused(self):
        self.assertIn("file has no row: b.txt", problems(small(GOOD_A), ["a.txt", "b.txt"]))

    def test_a_row_for_a_missing_file_is_refused(self):
        self.assertIn("row has no file: b.txt", problems(small(GOOD_A, GOOD_B), ["a.txt"]))

    def test_a_duplicate_row_is_refused(self):
        found = problems(small(GOOD_A, GOOD_A), ["a.txt"])
        self.assertTrue(any("appears twice: a.txt" in m for m in found))

    def test_an_unsorted_pair_is_refused(self):
        found = problems(small(GOOD_B, GOOD_A), ["a.txt", "b.txt"])
        self.assertIn("rows are not in ascending order of path", found)

    def test_a_fifth_column_is_refused(self):
        row = "| a.txt | claude-code | claude-sonnet-5-5 | 2026-11-01 | x |"
        found = problems(small(row), ["a.txt"])
        self.assertTrue(any("exactly four cells" in m for m in found))

    def test_a_header_with_another_column_name_is_refused(self):
        text = small(GOOD_A).replace("| path |", "| file |")
        self.assertTrue(any("header row" in m for m in problems(text, ["a.txt"])))

    def test_a_row_with_only_harness_filled_is_refused(self):
        row = "| a.txt | claude-code | not recorded | not recorded |"
        found = problems(small(row), ["a.txt"])
        self.assertTrue(any("partly filled" in m for m in found))

    def test_a_bad_date_is_refused(self):
        row = "| a.txt | claude-code | claude-sonnet-5-5 | 2026-02-30 |"
        found = problems(small(row), ["a.txt"])
        self.assertTrue(any("bad date" in m for m in found))

    def test_a_model_with_a_capital_letter_is_refused(self):
        row = "| a.txt | claude-code | Claude-Sonnet | 2026-11-01 |"
        found = problems(small(row), ["a.txt"])
        self.assertTrue(any("bad model" in m for m in found))

    def test_a_path_containing_a_pipe_is_refused(self):
        row = "| a|b.txt | claude-code | claude-sonnet-5-5 | 2026-11-01 |"
        found = problems(small(row), ["a|b.txt"])
        self.assertTrue(found)

    def test_git_failure_fails_loudly(self):
        saved = os.environ.get("PATH")
        os.environ["PATH"] = ""
        try:
            with self.assertRaises(AssertionError):
                repository_files()
        finally:
            os.environ["PATH"] = saved


if __name__ == "__main__":
    unittest.main()
