"""Tests that the guides and top-level documents cite no line numbers, and that every section
cite names a heading that exists. The parser is in this module, and it is tested on invented
text below. Fenced blocks and indented blocks are code and are skipped: tool output quoted in
a guide says things like `page 1 line 13`."""

import glob
import os
import re
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = ("README.md", "METHOD.md", "docs/record-model.md", "SUPPORT.md", "CONTRIBUTING.md",
       "AGENTS.md", "CHANGELOG.md", "CODE_OF_CONDUCT.md", "LICENSE-COMMERCIAL.md", "SECURITY.md")

LINE_CITE = re.compile(r"lines? [0-9]|\.md`?:[0-9]|#L[0-9]", re.IGNORECASE)
NUMBERED = re.compile(r'§ ([0-9]+(?:\.[0-9]+)?)(?:, "([^"]+)")?')
NAMED = re.compile(r'section "([^"]+)"')
LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)\s]*)?\)")
TICKS = re.compile(r"`([^`\s]+\.md)`")
HEADING = re.compile(r"^#{1,6} (.*)$")
MIN_CITES = 60


def documents(root):
    found = sorted(glob.glob(os.path.join(root, "docs", "guides", "*.md")))
    found += [os.path.join(root, name) for name in TOP]
    return found


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def fence_states(lines):
    """For each line, whether it is inside a fenced block (a fence line counts as inside)."""
    states = []
    open_fence = False
    for line in lines:
        is_fence = line.lstrip(" ").startswith(("```", "~~~"))
        states.append(open_fence or is_fence)
        if is_fence:
            open_fence = not open_fence
    return states


def prose(text):
    """A list of (line number, line) for the lines that are not code."""
    lines = text.split("\n")
    fenced = fence_states(lines)
    return [(i + 1, line) for i, line in enumerate(lines)
            if not fenced[i] and not line.startswith("    ")]


def headings(text):
    lines = text.split("\n")
    fenced = fence_states(lines)
    found = []
    for i, line in enumerate(lines):
        match = HEADING.match(line)
        if match and not fenced[i]:
            found.append(match.group(1).strip())
    return found


def line_number_cites(text):
    return ["%d: %s" % (number, line.strip()) for number, line in prose(text)
            if LINE_CITE.search(line)]


def line_targets(line, doc_dir, root):
    """The existing Markdown files a line names: link targets against the document's folder,
    backticked paths against that folder, the repository root and docs/."""
    found = []
    for target in LINK.findall(line):
        found.append(os.path.normpath(os.path.join(doc_dir, target)))
    for target in TICKS.findall(line):
        for base in (doc_dir, root, os.path.join(root, "docs")):
            found.append(os.path.normpath(os.path.join(base, target)))
    return [p for p in dict.fromkeys(found) if os.path.isfile(p)]


def cites_in(line):
    """A list of ('numbered', number, title or None) and ('named', None, title)."""
    found = [("numbered", m.group(1), m.group(2)) for m in NUMBERED.finditer(line)]
    found += [("named", None, m.group(1)) for m in NAMED.finditer(line)]
    return found


def resolves(cite, heads):
    kind, number, title = cite
    if kind == "named":
        return title in heads
    for head in heads:
        match = re.match(r"%s\.? (.*)$" % re.escape(number), head)
        if match and (title is None or match.group(1).strip() == title):
            return True
    return False


def check_document(path, root, cache):
    """Return (number of cites, list of unresolved cites as 'line: cite')."""
    text = read(path)
    doc_dir = os.path.dirname(path)
    rows = prose(text)
    named_anywhere = []
    for _, line in rows:
        named_anywhere += line_targets(line, doc_dir, root)
    named_anywhere = list(dict.fromkeys(named_anywhere))
    count = 0
    unresolved = []
    for number, line in rows:
        cites = cites_in(line)
        if not cites:
            continue
        own = line_targets(line, doc_dir, root)
        for cite in cites:
            count += 1
            ok = False
            for group in (own, named_anywhere):
                for target in group:
                    if target not in cache:
                        cache[target] = headings(read(target))
                    if resolves(cite, cache[target]):
                        ok = True
                        break
                if ok:
                    break
            if not ok:
                unresolved.append("%d: %s" % (number, "".join(
                    "%s " % part for part in cite if part).strip()))
    return count, unresolved


class Tree(unittest.TestCase):
    def test_the_documents_in_scope_exist(self):
        missing = [p for p in documents(ROOT) if not os.path.isfile(p)]
        with self.subTest(missing=", ".join(missing)):
            self.assertTrue(not missing, "a document in scope is not a file")

    def test_every_top_level_document_is_in_scope(self):
        listed = sorted(name for name in TOP if "/" not in name)
        found = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*.md")))
        self.assertTrue(listed == found,
                        "a top-level document is missing from TOP or is not a file")

    def test_no_document_cites_a_line_number(self):
        found = []
        for path in documents(ROOT):
            for item in line_number_cites(read(path)):
                found.append("%s line %s" % (os.path.relpath(path, ROOT), item))
        with self.subTest(findings="; ".join(found)):
            self.assertTrue(not found, "a document cites another file by line number")

    def test_every_section_cite_names_a_heading_that_exists(self):
        cache = {}
        total = 0
        found = []
        for path in documents(ROOT):
            count, unresolved = check_document(path, ROOT, cache)
            total += count
            found += ["%s line %s" % (os.path.relpath(path, ROOT), item) for item in unresolved]
        with self.subTest(findings="; ".join(found)):
            self.assertTrue(not found, "a section cite names a heading that does not exist")
        self.assertTrue(total >= MIN_CITES, "the parser found too few section cites")


class Parser(unittest.TestCase):
    def write(self, folder, name, text):
        path = os.path.join(folder, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_a_line_number_cite_outside_code_is_found(self):
        self.assertTrue(len(line_number_cites("See the spec, line 12.\n")) == 1,
                        "a cite by line number was not found")
        self.assertTrue(len(line_number_cites("See `docs/a.md`:12 now.\n")) == 1,
                        "a path:line cite was not found")

    def test_a_line_number_cite_in_another_case_or_as_an_anchor_is_found(self):
        self.assertTrue(len(line_number_cites("See the spec, Line 12.\n")) == 1,
                        "a capitalised cite by line number was not found")
        self.assertTrue(len(line_number_cites("See [the spec](spec.md#L12).\n")) == 1,
                        "a line anchor cite was not found")
        self.assertTrue(len(line_number_cites("See LINES 3 to 5.\n")) == 1,
                        "an upper-case cite by line numbers was not found")
        self.assertTrue(line_number_cites("The page has twelve lines.\n") == [],
                        "a line count in words was found as a cite")

    def test_the_same_text_in_a_fenced_block_is_not_found(self):
        self.assertTrue(line_number_cites("```\npage 1 line 13\n```\n") == [],
                        "a line number in a backtick block was found")
        self.assertTrue(line_number_cites("~~~\npage 1 line 13\n~~~\n") == [],
                        "a line number in a tilde block was found")

    def test_the_same_text_in_an_indented_block_is_not_found(self):
        self.assertTrue(line_number_cites("Text.\n\n    page 1 line 13\n") == [],
                        "a line number in an indented block was found")

    def test_a_cite_of_a_section_that_does_not_exist_is_unresolved(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "docs/spec.md", "# Spec\n\n## 2. Scope\n")
            doc = self.write(folder, "docs/guides/a.md",
                             'See [the spec](../spec.md), § 9, "Nowhere".\n')
            count, unresolved = check_document(doc, folder, {})
        self.assertTrue(count == 1 and len(unresolved) == 1, "a missing section did not fail")

    def test_a_cite_of_a_section_that_exists_resolves(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "docs/spec.md", "# Spec\n\n## 2. Scope\n\n## Other part\n")
            doc = self.write(folder, "docs/guides/a.md", (
                'See [the spec](../spec.md), § 2, "Scope", and section "Other part".\n'
                "Also § 2.\n"))
            count, unresolved = check_document(doc, folder, {})
        self.assertTrue(count == 3 and unresolved == [], "a section that exists did not resolve")

    def test_a_wrong_title_for_a_number_is_unresolved(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "docs/spec.md", "# Spec\n\n## 2. Scope\n")
            doc = self.write(folder, "docs/guides/a.md",
                             'See [the spec](../spec.md), § 2, "Not the title".\n')
            _, unresolved = check_document(doc, folder, {})
        self.assertTrue(len(unresolved) == 1, "a wrong title resolved")

    def test_a_cite_resolves_through_a_file_named_elsewhere_in_the_document(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "docs/spec.md", "# Spec\n\n## 2. Scope\n")
            self.write(folder, "docs/guides/other.md", "# Other\n")
            doc = self.write(folder, "docs/guides/a.md", (
                "The spec is `docs/spec.md`.\n"
                'Here, [other](other.md) and the same spec, § 2, "Scope".\n'
                'And with no target: the same spec, § 2, "Scope".\n'))
            count, unresolved = check_document(doc, folder, {})
        self.assertTrue(count == 2 and unresolved == [],
                        "a cite did not resolve through a file named elsewhere")

    def test_a_heading_inside_a_fenced_block_is_not_a_heading(self):
        self.assertTrue(headings("```\n## 2. Scope\n```\n") == [],
                        "a heading in a fenced block was read as a heading")


if __name__ == "__main__":
    unittest.main()
