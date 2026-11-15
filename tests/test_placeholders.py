"""Gate: no file in the repository holds the placeholder marker.

A sentence that its owner has still to word is written with the marker, which is the two words
below with any run of characters that are neither letters nor digits between them, in any case:
a hyphen, a space, an underscore, a dash that is not ASCII, a line break. This test fails,
naming each file, while any file holds it, so the sentence cannot ship unworded. Each word is
built from pieces at run time, so this file never holds either word whole, and neither does its
compiled copy: a compiler would join two constants that are added in the source.

A file is read as UTF-16 when it starts with a UTF-16 byte-order mark and as UTF-8 otherwise,
with bytes that do not decode replaced. The ``.git`` folder at the top and every
``__pycache__`` folder are skipped.
"""

import os
import re
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRST = "".join(["unw", "orded"])
SECOND = "".join(["place", "holder"])
MARKER = re.compile(FIRST + r"[\W_]*" + SECOND, re.IGNORECASE)
UTF16_MARKS = (b"\xff\xfe", b"\xfe\xff")


def text_of(data):
    """The text of a file's bytes: UTF-16 after a UTF-16 byte-order mark, else UTF-8."""
    if data.startswith(UTF16_MARKS):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def marked_files(root):
    """Sorted relative paths, with ``/`` as the separator, of every file under ``root`` (outside
    the top ``.git`` and any ``__pycache__``) whose text holds the marker."""
    found = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs
                   if d != "__pycache__" and not (folder == root and d == ".git")]
        for name in names:
            path = os.path.join(folder, name)
            shown = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, "rb") as handle:
                    data = handle.read()
            except OSError:
                found.append(shown + " (unreadable)")
                continue
            if MARKER.search(text_of(data)):
                found.append(shown)
    return sorted(found)


def written(root, files):
    for name, content in files.items():
        path = os.path.join(root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)


class PlaceholderCase(unittest.TestCase):
    def test_no_file_holds_the_placeholder_marker(self):
        self.assertEqual(marked_files(ROOT), [],
                         "these files still hold a sentence its owner has not worded")

    def test_the_walk_finds_the_marker_however_it_is_written(self):
        one, two = FIRST, SECOND
        files = {
            "lower.md": ("x %s-%s y" % (one, two)).encode(),
            "upper.md": ("%s %s" % (one.upper(), two.upper())).encode(),
            "mixed.md": ("%s %s" % (one.capitalize(), two.capitalize())).encode(),
            "underscore.md": ("%s_%s" % (one, two)).encode(),
            "dash.md": ("%s%s%s" % (one, chr(0x2011), two)).encode("utf-8"),
            "emdash.md": ("%s %s %s" % (one, chr(0x2014), two)).encode("utf-8"),
            "utf16.md": ("%s %s" % (one, two)).encode("utf-16"),
            "utf16be.md": b"\xfe\xff" + ("%s %s" % (one, two)).encode("utf-16-be"),
            "lines.md": ("%s\n%s" % (one, two)).encode(),
            "crlf.md": ("%s\r\n%s" % (one, two)).encode(),
            "joined.md": (one + two).encode(),
            "runs.md": ("%s - _ \n\t%s" % (one, two)).encode(),
            "bad.bin": b"\xff\xff" + ("%s %s" % (one, two)).encode() + b"\xff",
            "a/b/deep.txt": ("x %s-%s y" % (one, two)).encode(),
        }
        with tempfile.TemporaryDirectory() as root:
            written(root, files)
            self.assertEqual(marked_files(root), sorted(files))

    def test_the_walk_skips_the_top_git_folder_and_every_pycache_folder(self):
        marker = ("%s-%s" % (FIRST, SECOND)).encode()
        with tempfile.TemporaryDirectory() as root:
            written(root, {".git/config": marker, "__pycache__/x.pyc": marker,
                           "a/__pycache__/y.pyc": marker, "sub/.git/note": marker,
                           "top.bin": b"\x00\xff" + marker})
            self.assertEqual(marked_files(root), ["sub/.git/note", "top.bin"])

    def test_the_walk_does_not_join_words_that_a_letter_or_a_digit_separates(self):
        one, two = FIRST, SECOND
        with tempfile.TemporaryDirectory() as root:
            written(root, {
                "clean.md": b"nothing here\n",
                "letter.md": ("%s-x-%s" % (one, two)).encode(),
                "digit.md": ("%s1%s" % (one, two)).encode(),
                "accent.md": ("%s%s%s" % (one, chr(0xE9), two)).encode("utf-8"),
                "half.md": ("%s\n-\n" % one).encode(),
                "other.md": ("%s %s" % (two, one)).encode(),
            })
            self.assertEqual(marked_files(root), [])

    def test_the_walk_of_a_clean_tree_is_empty(self):
        with tempfile.TemporaryDirectory() as root:
            written(root, {"one.txt": b"clean"})
            self.assertEqual(marked_files(root), [])

    def test_this_file_does_not_hold_the_marker(self):
        with open(os.path.abspath(__file__), "rb") as handle:
            self.assertIsNone(MARKER.search(text_of(handle.read())))


if __name__ == "__main__":
    unittest.main()
