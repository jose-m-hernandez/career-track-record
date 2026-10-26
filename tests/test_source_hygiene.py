"""Hygiene test: no Python file under tests/ holds a raw invisible character.

Invisible characters (format, line-separator and paragraph-separator characters, and the
no-break space) are written as escapes in test sources, so a reviewer can read them and a
hidden character cannot change what the code appears to say. This file writes every such
character with chr(), never raw, because it scans itself."""

import os
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
MIN_FILES = 15


def raw_invisibles(text):
    """Return (line number, "U+XXXX") for each Cf, Zl or Zp character, or U+00A0."""
    found = []
    line = 1
    for char in text:
        if unicodedata.category(char) in ("Cf", "Zl", "Zp") or char == chr(0xA0):
            found.append((line, "U+%04X" % ord(char)))
        if char == "\n":
            line += 1
    return found


def python_files():
    found = []
    for root, dirs, files in os.walk(TESTS):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            if name.endswith(".py"):
                found.append(os.path.join(root, name))
    return found


class SourceHygieneCase(unittest.TestCase):
    def test_no_test_source_holds_a_raw_invisible_character(self):
        files = python_files()
        self.assertGreaterEqual(len(files), MIN_FILES)
        for path in files:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            name = os.path.relpath(path, ROOT).replace(os.sep, "/")
            self.assertEqual(raw_invisibles(text), [],
                             "%s holds a raw invisible character" % name)

    def test_the_helper_finds_each_kind(self):
        planted = [
            (chr(0x200B), "U+200B"),
            (chr(0x2028), "U+2028"),
            (chr(0x2029), "U+2029"),
            (chr(0x00A0), "U+00A0"),
            (chr(0x00AD), "U+00AD"),
        ]
        for char, label in planted:
            with self.subTest(label):
                text = "one\ntwo\nth" + char + "ree\nfour\n"
                self.assertEqual(raw_invisibles(text), [(3, label)])
        self.assertEqual(raw_invisibles("plain\ttab\nsecond line\n"), [])


if __name__ == "__main__":
    unittest.main()
