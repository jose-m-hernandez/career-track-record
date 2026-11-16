"""Tests that the drafts guide agrees with ``track-record drafts``. Every example here is invented.

Each run the drafts guide shows is repeated on the fixtures, in a
temporary folder with the run folder made, and what it prints is compared with the guide.
"""

import os
import unittest

from tests import test_drafts as d
from tests.test_record_check import ROOT, fenced_after, read

GUIDE = os.path.join(ROOT, "docs", "guides", "drafts.md")
README = os.path.join(ROOT, "README.md")
HEADING = "# `track-record drafts`"
PREFIX = "    track-record drafts "


def section():
    text = read(GUIDE)
    start = text.index(HEADING)
    return text[start:].split("\n")


def shown_runs():
    """[(command words after ``track-record``, the lines the guide shows under it)]."""
    lines = section()
    runs = []
    for index, line in enumerate(lines):
        if not line.startswith(PREFIX):
            continue
        shown = []
        for after in lines[index + 1:]:
            if not after.startswith("    ") or after.startswith(PREFIX):
                break
            shown.append(after[4:])
        runs.append((line[len("    track-record "):].split(), shown))
    return runs


class DocsTest(d.DraftsCase):
    def test_the_readme_shows_the_known_answers(self):
        commands = [" ".join(words) for words, _shown in shown_runs()]
        self.assertIn("drafts check letter.txt --earlier letter-before.txt", commands)
        self.assertIn("drafts check letter-edited.txt --earlier letter-before.txt", commands)

    def test_each_run_the_readme_shows_prints_what_it_shows(self):
        for words, shown in shown_runs():
            with self.subTest(" ".join(words)):
                self.work()
                code, out, err = self.cli(words)
                want = "".join(line + "\n" for line in shown)
                self.assertEqual(out + err, want)

    def test_the_readme_ok_line_is_the_specs_known_answer(self):
        runs = dict((" ".join(words), shown) for words, shown in shown_runs())
        self.assertEqual(runs["drafts check letter.txt --earlier letter-before.txt"],
                         [d.OK_LINE])

    def test_the_readme_names_the_spec_and_the_command(self):
        text = "\n".join(section())
        self.assertIn("(../specs/drafts.md)", text)
        self.assertIn("`track-record drafts check FILE [--earlier COPY]`", text)
        self.assertIn("`track-record drafts extract FILE ID --out OUT [--earlier COPY]`", text)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "docs", "specs", "drafts.md")))

    def test_the_readme_example_is_the_known_fixture(self):
        text = read(GUIDE)
        section_text = text[text.index(HEADING):]
        self.assertEqual(fenced_after(section_text, HEADING),
                         read(os.path.join(ROOT, "tests", "fixtures", "drafts", "letter.txt")))

    def test_the_section_comes_after_the_record_section(self):
        text = read(README)
        self.assertLess(text.index("(docs/guides/record.md)"), text.index("(docs/guides/drafts.md)"))
        self.assertLess(text.index("(docs/guides/drafts.md)"), text.index("(docs/guides/panel.md)"))


if __name__ == "__main__":
    unittest.main()
