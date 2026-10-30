"""Pin test: each behaviour spec's Revision line matches an explicit map in this file.

A change to a spec's `Revision:` line must update SPEC_REVISIONS in the same change. A spec
with no Revision line is listed as EXEMPT. The test does not read the CHANGELOG."""

import os
import re
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXEMPT = "EXEMPT"
SPEC_REVISIONS = {
    "barred.md": "6.3",
    "cli.md": "2",
    "keyword-scan.md": EXEMPT,
    "reader-ab.md": "1",
    "tone-and-tells.md": "6",
}

REVISION_LINE = re.compile(r"^Revision: (\d+(?:\.\d+)*)\.( |$)")


def header_revisions(text):
    """The revisions named by the `Revision:` lines of the header (before the first `## `).

    A readable line gives its revision string; any other `Revision:` line gives None."""
    found = []
    for line in text.split("\n"):
        if line.startswith("## "):
            break
        if line.startswith("Revision:"):
            match = REVISION_LINE.match(line)
            found.append(match.group(1) if match else None)
    return found


def revision_problems(spec_dir, expected):
    """Sorted problem messages for the *.md files directly in spec_dir against expected."""
    problems = []
    names = sorted(n for n in os.listdir(spec_dir)
                   if n.endswith(".md") and os.path.isfile(os.path.join(spec_dir, n)))
    for name in sorted(set(names) | set(expected)):
        label = "docs/specs/" + name
        if name not in names:
            problems.append(label + ": SPEC_REVISIONS has a row but the file is missing")
            continue
        with open(os.path.join(spec_dir, name), encoding="utf-8") as handle:
            revisions = header_revisions(handle.read())
        if len(revisions) > 1 or revisions == [None]:
            problems.append(label + ": Revision line not readable")
            continue
        found = revisions[0] if revisions else "none"
        if name not in expected:
            problems.append("%s: no row in SPEC_REVISIONS (Revision line says %s)"
                            % (label, found))
            continue
        want = expected[name]
        if found != ("none" if want == EXEMPT else want):
            problems.append("%s: Revision line says %s, SPEC_REVISIONS expects %s"
                            % (label, found, want))
    return sorted(problems)


class SpecRevisionCase(unittest.TestCase):
    def test_each_spec_matches_its_row(self):
        spec_dir = os.path.join(ROOT, "docs", "specs")
        self.assertEqual(revision_problems(spec_dir, SPEC_REVISIONS), [])

    def test_the_checker_finds_each_problem(self):
        def says(name, found, want):
            return ("docs/specs/%s: Revision line says %s, SPEC_REVISIONS expects %s"
                    % (name, found, want))

        cases = [
            ("matching revision", {"a.md": "# A\n\nRevision: 2. Text.\n"},
             {"a.md": "2"}, []),
            ("wrong revision", {"a.md": "# A\n\nRevision: 3. Text.\n"},
             {"a.md": "2"}, [says("a.md", "3", "2")]),
            ("exempt without a line", {"a.md": "# A\n\nNo revision here.\n"},
             {"a.md": EXEMPT}, []),
            ("exempt with a line", {"a.md": "# A\n\nRevision: 1.\n"},
             {"a.md": EXEMPT}, [says("a.md", "1", EXEMPT)]),
            ("row without a line", {"a.md": "# A\n\nNo revision here.\n"},
             {"a.md": "2"}, [says("a.md", "none", "2")]),
            ("prefix is not a match", {"a.md": "# A\n\nRevision: 6.1.\n"},
             {"a.md": "6"}, [says("a.md", "6.1", "6")]),
            ("file with no row",
             {"a.md": "# A\n\nRevision: 1.\n", "b.md": "# B\n\nRevision: 1.\n"},
             {"a.md": "1"},
             ["docs/specs/b.md: no row in SPEC_REVISIONS (Revision line says 1)"]),
            ("row with no file", {}, {"a.md": "2"},
             ["docs/specs/a.md: SPEC_REVISIONS has a row but the file is missing"]),
            ("two Revision lines",
             {"a.md": "# A\n\nRevision: 1.\nRevision: 2.\n"}, {"a.md": "2"},
             ["docs/specs/a.md: Revision line not readable"]),
            ("unreadable Revision line", {"a.md": "# A\n\nRevision: soon\n"},
             {"a.md": "2"}, ["docs/specs/a.md: Revision line not readable"]),
            ("only the header counts",
             {"a.md": "# A\n\nNo revision here.\n\n## Later\n\nRevision: 9.\n"},
             {"a.md": EXEMPT}, []),
            ("only *.md directly in the folder",
             {"a.md": "# A\n\nRevision: 2.\n", "notes.txt": "Revision: 5.\n",
              "old/x.md": "# X\n\nRevision: 7.\n"},
             {"a.md": "2"}, []),
        ]
        for label, files, expected, want in cases:
            with self.subTest(label):
                with tempfile.TemporaryDirectory() as spec_dir:
                    for name, content in files.items():
                        path = os.path.join(spec_dir, *name.split("/"))
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, "w", encoding="utf-8") as handle:
                            handle.write(content)
                    self.assertEqual(revision_problems(spec_dir, expected), want)


if __name__ == "__main__":
    unittest.main()
