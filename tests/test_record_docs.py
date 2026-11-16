"""Tests that the record guide and docs/record-model.md agree with the record check. Every example
here is invented.

The guide's run, its declaration and the record model's declaration are read from those files
and compared with what the tool does.
"""

import os
import sys
import unittest

from tests.test_record_check import KNOWN, ROOT, RecordCase, fenced_after, read

sys.path.insert(0, os.path.join(ROOT, "src"))

from career_track_record import record_check  # noqa: E402

GUIDE = os.path.join(ROOT, "docs", "guides", "record.md")


class DocsTest(RecordCase):
    def test_the_readme_block_equals_the_run(self):
        text = read(GUIDE)
        section = text[text.index("# `track-record record`"):]
        lines = section.split("\n")
        start = lines.index("    track-record record record.txt") + 1
        block = []
        for line in lines[start:]:
            block.append(line)
            if line.startswith("    checks:"):
                break
        self.assertTrue(all(line.startswith("    ") for line in block))
        code, out, _err = self.cli(["record", os.path.join(KNOWN, "record.txt")])
        self.assertEqual("".join(line[4:] + "\n" for line in block), out)

    def test_the_readme_declaration_is_the_known_fixture(self):
        text = read(GUIDE)
        section_text = text[text.index("# `track-record record`"):]
        self.assertEqual(fenced_after(section_text, "This one is invented:"),
                         read(os.path.join(KNOWN, "record.txt")))

    def test_the_record_model_declaration_has_no_problem(self):
        text = read(os.path.join(ROOT, "docs", "record-model.md"))
        block = fenced_after(text, "The declaration that checks it")
        decl, problems = record_check.parse_declaration(block)
        self.assertEqual(problems, [])
        self.assertEqual([t[0] for t in decl.tables],
                         ["entries", "origins", "resolutions", "notes", "claims"])
        self.assertEqual(len(decl.references), 4)

    def test_the_record_model_example_has_seven_nodes_in_both_drawings(self):
        text = read(os.path.join(ROOT, "docs", "record-model.md"))
        mermaid = fenced_after(text, "Seven nodes.")
        plain = fenced_after(text, "The same graph in plain text")
        for node in ("c-01", "e-02", "e-01", "o-01", "o-02", "r-01", "n-01"):
            self.assertIn(node, mermaid)
            self.assertIn(node, plain)


if __name__ == "__main__":
    unittest.main()
