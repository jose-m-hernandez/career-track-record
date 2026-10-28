"""Barred-wording check: where a file uses wording from the user's own barred list.

The behaviour is stated in docs/specs/barred.md. In short: fold the list and each
file's text (and name), compare in three forms, report entry numbers and line numbers
only, and call a file clean only when it was read in full and passed its control.

Nothing here prints an entry, a note, matched text, a matching path or the list's path.
"""

import collections
import os
import re
import unicodedata

from career_track_record import pdf_text

Entry = collections.namedtuple("Entry", "number folded word")

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_CANARY = re.compile(r"barred-strings-canary-[a-z0-9]{8,}")


class ListError(Exception):
    """The list cannot be used. The message is safe to print: no entry, no path."""


class Result(object):
    """What a run produced. ``text`` is exactly stdout; ``error`` is the one stderr line."""

    def __init__(self, exit_code, ran, text="", error=""):
        self.exit_code = exit_code
        self.ran = ran
        self.text = text
        self.error = error

    def __repr__(self):
        return "Result(exit_code=%r, ran=%r, error=%r)" % (
            self.exit_code, self.ran, self.error)


def _cannot(message):
    return Result(2, False, text="", error="cannot run: " + message)


# ---------------------------------------------------------------- folding

def fold(text):
    """NFKC, full case folding, NFKC again, then drop every format character (Cf)."""
    text = unicodedata.normalize("NFKC", text)
    text = unicodedata.normalize("NFKC", text.casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def prepare(text):
    """Fold, turn every whitespace run into one space, trim (spec section 4)."""
    return " ".join(fold(text).split())


def _fold_with_lines(text):
    """Fold each source line on its own; return (folded text, line of each folded char).

    Line breaks (LF, CRLF, lone CR) become one LF each; nothing else is a break."""
    chars = []
    lines = []
    parts = _LINE_BREAK.split(text)
    last = len(parts) - 1
    for index, part in enumerate(parts):
        number = index + 1
        folded = fold(part)
        chars.append(folded)
        lines.extend([number] * len(folded))
        if index != last:
            chars.append("\n")
            lines.append(number)
    return "".join(chars), lines


def _is_word_char(ch):
    return ch == "_" or unicodedata.category(ch)[0] in ("L", "N")


def _is_boundary(ch):
    category = unicodedata.category(ch)
    return not (category[0] == "L" or category == "Nd")


def _collapse(text, lines):
    out = []
    out_lines = []
    in_space = False
    for ch, number in zip(text, lines):
        if ch.isspace():
            if not in_space:
                out.append(" ")
                out_lines.append(number)
            in_space = True
        else:
            out.append(ch)
            out_lines.append(number)
            in_space = False
    return "".join(out), out_lines


def _rejoin(text, lines):
    """Remove a hyphen-minus that ends a line inside a word, with the whitespace after it."""
    size = len(text)
    out = []
    out_lines = []
    i = 0
    while i < size:
        ch = text[i]
        if ch == "-" and i > 0 and _is_word_char(text[i - 1]):
            j = i + 1
            while j < size and text[j] in " \t":
                j += 1
            if j < size and text[j] == "\n":
                j += 1
                while j < size and text[j].isspace():
                    j += 1
                if j < size and _is_word_char(text[j]):
                    i = j
                    continue
        out.append(ch)
        out_lines.append(lines[i])
        i += 1
    return "".join(out), out_lines


def _keep_hyphen(text, lines):
    """Keep a hyphen-minus that ends a line inside a word; remove the break after it.

    After the hyphen only spaces, tabs or form feeds may come, then one line break, then
    any whitespace, then a word character. The hyphen stays; the rest is removed."""
    size = len(text)
    out = []
    out_lines = []
    i = 0
    while i < size:
        ch = text[i]
        out.append(ch)
        out_lines.append(lines[i])
        if ch == "-" and i > 0 and _is_word_char(text[i - 1]):
            j = i + 1
            while j < size and text[j] in " \t\f":
                j += 1
            if j < size and text[j] == "\n":
                j += 1
                while j < size and text[j].isspace():
                    j += 1
                if j < size and _is_word_char(text[j]):
                    i = j
                    continue
        i += 1
    return "".join(out), out_lines


def _forms(text):
    """The joined, rejoined and hyphen-kept forms of a text, with the line of every character."""
    folded, lines = _fold_with_lines(text)
    joined = _collapse(folded, lines)
    rejoined = _collapse(*_rejoin(folded, lines))
    kept = _collapse(*_keep_hyphen(folded, lines))
    return joined, rejoined, kept


def _count(entry, form):
    """(count, line of the earliest match or None) of one entry in one form."""
    text, lines = form
    needle = entry.folded
    size = len(needle)
    count = 0
    first = None
    pos = 0
    while True:
        at = text.find(needle, pos)
        if at < 0:
            break
        if entry.word:
            before = at == 0 or _is_boundary(text[at - 1])
            end = at + size
            after = end >= len(text) or _is_boundary(text[end])
            if not (before and after):
                pos = at + 1
                continue
        if first is None:
            first = lines[at]
        count += 1
        pos = at + size
    return count, first


def _match(entry, forms):
    """(count, line) over all three forms: the larger count, the earlier line."""
    best = 0
    line = None
    for form in forms:
        count, first = _count(entry, form)
        best = max(best, count)
        if first is not None and (line is None or first < line):
            line = first
    return best, line


# ---------------------------------------------------------------- the list

def load_list(path):
    """Read the list file; return its entries. Raises ListError with a safe message."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (OSError, ValueError, TypeError):
        raise ListError("the list file cannot be read")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ListError("the list is not valid UTF-8")
    if text.startswith("﻿"):
        text = text[1:]
    entries = []
    for line in _LINE_BREAK.split(text):
        stripped = line.strip()
        if stripped == "" or stripped[0] == "#":
            continue
        number = len(entries) + 1
        fields = line.split("\t")
        flag = fields[1] if len(fields) > 1 else ""
        word = flag.lower() == "word"
        folded = prepare(fields[0])
        if folded == "":
            raise ListError("entry %d is empty" % number)
        if number == 1 and word and _CANARY.fullmatch(folded):
            raise ListError("entry 1 is a canary and cannot carry the word flag")
        entries.append(Entry(number, folded, word))
    if not entries:
        raise ListError("the list has no entries")
    return entries


# ---------------------------------------------------------------- stripping

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(?:(?<=\s)|\A)//[^\r\n]*")
_STRING = r'"(?:[^"\\]|\\.)*"'
_NOTE_VALUE = re.compile(
    r"(?<!\w)note:\s*(" + _STRING + r"(?:\s*\+\s*" + _STRING + r")*)", re.DOTALL)


def _blank(span):
    return "".join(ch if ch in "\r\n" else " " for ch in span)


def strip_comments(text):
    text = _BLOCK_COMMENT.sub(lambda m: _blank(m.group(0)), text)
    text = _LINE_COMMENT.sub(lambda m: _blank(m.group(0)), text)

    def note(match):
        whole = match.group(0)
        start = match.start(1) - match.start(0)
        return whole[:start] + _blank(whole[start:])

    return _NOTE_VALUE.sub(note, text)


# ---------------------------------------------------------------- one file

class _Dead(Exception):
    pass


def _read_text(path, strip):
    if path.lower().endswith(".pdf"):
        try:
            with open(path, "rb"):
                pass
        except (OSError, ValueError):
            raise _Dead("cannot read")
        target = "./" + path if path.startswith("-") else path
        try:
            return pdf_text.pdf_text(target)
        except pdf_text.PdfTextError as exc:
            raise _Dead("pdftotext " + exc.reason)
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (OSError, ValueError):
        raise _Dead("cannot read")
    text = data.decode("utf-8", errors="replace")
    return strip_comments(text) if strip else text


def _is_the_list(path, list_path):
    try:
        return os.path.samefile(path, list_path)
    except (OSError, ValueError):
        return False


_SIMPLE_ESCAPES = {"\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def printed_path(path):
    """The path as given, with the characters of spec section 6 escaped in one pass."""
    out = []
    for ch in path:
        if ch in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[ch])
            continue
        code = ord(ch)
        category = unicodedata.category(ch)
        if category == "Cc":
            out.append("\\x%02x" % code)
        elif category == "Cf" or code in (0x2028, 0x2029):
            out.append("\\u%04x" % code if code <= 0xFFFF else "\\U%08x" % code)
        else:
            out.append(ch)
    return "".join(out)


def _name_hits(name, entries):
    forms = _forms(name)
    return [e for e in entries if _match(e, forms)[0] > 0]


def _check_file(position, path, entries, controls, strip, min_chars, list_path):
    shown = printed_path(path)
    by_path = set(e.number for e in _name_hits(path, entries))
    by_shown = set(e.number for e in _name_hits(shown, entries))
    name_hits = [e for e in entries if e.number in by_path | by_shown]
    label = ("file #%d" % position
             if name_hits or _is_the_list(path, list_path) else shown)
    try:
        try:
            text = _read_text(path, strip)
            joined, rejoined, kept = _forms(text)
        except _Dead:
            raise
        except Exception:
            raise _Dead("cannot read")
        length = len(joined[0])
        if length < min_chars:
            raise _Dead("too short (%d chars, minimum %d)" % (length, min_chars))
        if not any(c in joined[0] for c in controls):
            raise _Dead("control not found")
    except _Dead as dead:
        return "DEAD", ["DEAD  %s: %s" % (label, dead.args[0])]
    found = []
    for entry in entries:
        count, line = _match(entry, (joined, rejoined, kept))
        if count > 0:
            found.append((entry.number, line, count))
    if not name_hits and not found:
        return "OK", ["OK    %s: 0 of %d entries (control found; %d chars)"
                      % (label, len(entries), length)]
    distinct = len(set(e.number for e in name_hits) | set(n for n, _l, _c in found))
    out = ["FAIL  %s: %d entries" % (label, distinct)]
    for entry in name_hits:
        out.append("%s:0: entry #%d (file name)" % (label, entry.number))
    for number, line, count in found:
        out.append("%s:%d: entry #%d (%d x)" % (label, line, number, count))
    return "FAIL", out


# ---------------------------------------------------------------- the run

def run(*, list_path, files, controls, strip_comments=False, min_chars=500):
    try:
        return _run(list_path, list(files), list(controls), strip_comments, min_chars)
    except Exception:
        return _cannot("internal error")


def _run(list_path, files, controls, strip, min_chars):
    if not files:
        return _cannot("no input file")
    if not controls:
        return _cannot("no --control given")
    if not any(prepare(c) != "" for c in controls):
        return _cannot("no usable --control given")
    if not list_path:
        return _cannot("no list (give --list or set BARRED_STRINGS_PATH)")
    try:
        entries = load_list(list_path)
    except ListError as exc:
        return _cannot(str(exc))
    folded_controls = [c for c in (prepare(c) for c in controls) if c != ""]
    lines = []
    kinds = set()
    for position, path in enumerate(files, 1):
        kind, out = _check_file(position, path, entries, folded_controls, strip,
                                min_chars, list_path)
        kinds.add(kind)
        lines.extend(out)
    if "DEAD" in kinds:
        code = 2
    elif "FAIL" in kinds:
        code = 1
    else:
        code = 0
    return Result(code, True, text="".join(line + "\n" for line in lines))
