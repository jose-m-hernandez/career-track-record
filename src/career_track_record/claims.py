"""Claim gate: fail on any sentence your claims list has not approved.

The behaviour is stated in docs/specs/claims.md. In short: read the claims list, cut each
input file into blocks and sentences, and call a sentence approved only when an entry with
the status ``approved`` equals it, exactly, after folding. A file is called clean only when
it was read in full, held a control and held at least one sentence to check.

With ``check_sources`` (``--check-sources``), each approved or proposed entry that has a quote
line also has its quote checked, through ``quote_check``, against the source file it cites, a
path relative to the list's folder. This ports an evidence-check method in which a quote must
appear in the source it cites.

Output names an entry only by its number. It never holds a source, a resolved source path,
text read from a source, a quote, a note, the list's path or the sentence of an entry that
covered nothing.
"""

import bisect
import os
import re
import unicodedata

from career_track_record import barred
from career_track_record.barred import (
    _Dead, _is_the_list, _keep_hyphen, _read_text, fold, printed_path,
)
from career_track_record.tone import _CLOSERS, _line_starts, _sentence_ends

_STATUSES = ("approved", "proposed", "refused")
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_MARKER = re.compile(r"[ \t]*(?:[-*+\u2022]|[0-9]{1,3}[.)]|#{1,6})[ \t]+")
_EXTRA_FOLDS = {0x2010: "-", 0x2011: "-", 0x2018: "'", 0x2019: "'",
                0x201C: '"', 0x201D: '"'}


class ListError(Exception):
    """The list cannot be used. The message is safe to print: no entry text, no path."""


def _cannot(message):
    return barred.Result(2, False, text="", error="cannot run: " + message)


# ---------------------------------------------------------------- preparing text

def _fold(text):
    """Barred's folding, then the two further steps of spec section 4."""
    return fold(text).translate(_EXTRA_FOLDS)


def _squash(text):
    """Fold, join line-end hyphens (barred form 3), turn whitespace runs into one space, trim.

    Line breaks of every kind count as one LF before the join looks for them."""
    text = _LINE_BREAK.sub("\n", text)
    folded = _fold(text)
    joined, _ = _keep_hyphen(folded, [0] * len(folded))
    return " ".join(joined.split())


def _drop_final(text):
    """Remove one final ``.``, ``!`` or ``?`` and any closing characters after it."""
    end = len(text)
    while end > 0 and text[end - 1] in _CLOSERS:
        end -= 1
    if end > 0 and text[end - 1] in ".!?":
        return text[:end - 1]
    return text


def prepare(text):
    """The prepared form of a run or of an entry's sentence."""
    return _drop_final(_squash(text))


def prepare_control(text):
    """The prepared form of a control: the same, without the final full stop removed."""
    return _squash(text)


# ---------------------------------------------------------------- the list

def load_list(path):
    """Read the list file; return its entries as (number, status, prepared sentence)."""
    return _read_list(path)[0]


def _read_list(path):
    """Read the list file; return (entries, quotes).

    ``entries`` is what ``load_list`` returns. ``quotes`` holds one (number, status, source,
    quote) for each entry with a quote line, in entry order: the source is the entry's third
    field trimmed, the quote the quote line's second field as written.

    A quote is a line of its own, ``quote<TAB>text``, under the entry it belongs to, and not a
    fourth field of the entry: anything after an entry's third tab has always been a note, so a
    fourth-field quote would change the meaning of lists that already carry notes. ``quote`` is
    an unknown status to a list reader without quote lines, so no list it accepted changes
    meaning. A quote line takes no entry number."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (OSError, ValueError, TypeError):
        raise ListError("the list file cannot be read")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ListError("the list is not valid UTF-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    entries = []
    sources = {}
    quoted = {}
    for line in _LINE_BREAK.split(text):
        stripped = line.strip()
        if stripped == "" or stripped[0] == "#":
            continue
        number = len(entries) + 1
        fields = line.split("\t")
        status = fields[0].strip().lower()
        if status == "quote":
            owner = len(entries)
            if owner == 0:
                raise ListError("a quote line comes before the first entry")
            if owner in quoted:
                raise ListError("entry #%d has two quote lines" % owner)
            if sources.get(owner, "") == "":
                raise ListError("entry #%d has a quote but no source" % owner)
            if len(fields) < 2 or not _has_letter_or_digit(prepare(fields[1])):
                raise ListError("entry #%d has an empty quote" % owner)
            quoted[owner] = fields[1]
            continue
        if status not in _STATUSES:
            raise ListError("unknown status in entry #%d" % number)
        prepared = prepare(fields[1]) if len(fields) > 1 else ""
        if prepared == "":
            raise ListError("entry #%d has no sentence" % number)
        entries.append((number, status, prepared))
        sources[number] = fields[2].strip() if len(fields) > 2 else ""
    first = {}
    for number, _status, prepared in entries:
        if prepared in first:
            raise ListError("entries #%d and #%d are the same sentence"
                            % (first[prepared], number))
        first[prepared] = number
    quotes = [(number, status, sources[number], quoted[number])
              for number, status, _prepared in entries if number in quoted]
    return entries, quotes


# ---------------------------------------------------------------- one file's text

def _working(text):
    """Fold a file's text for finding blocks and sentences.

    Folding is done one character at a time, with the combining marks after it, so that each
    folded character knows the span of the source it came from. Every line break (CRLF, lone
    CR, LF) becomes one LF with the span of the break. Returns (folded text, spans)."""
    chars = []
    spans = []
    size = len(text)
    i = 0
    while i < size:
        ch = text[i]
        if ch == "\r":
            j = i + 2 if text.startswith("\r\n", i) else i + 1
            chars.append("\n")
            spans.append((i, j))
            i = j
            continue
        if ch == "\n":
            chars.append("\n")
            spans.append((i, i + 1))
            i += 1
            continue
        j = i + 1
        while j < size and unicodedata.combining(text[j]) != 0:
            j += 1
        if j == i + 1 and ch.isascii():
            folded = ch.lower()
        else:
            folded = _fold(text[i:j])
        for item in folded:
            chars.append(item)
            spans.append((i, j))
        i = j
    return "".join(chars), spans


def _blocks(text):
    """The (start, end) of each block of the joined text; line markers are left out."""
    blocks = []
    current = None
    size = len(text)
    pos = 0
    while True:
        newline = text.find("\n", pos)
        end = size if newline < 0 else newline
        line = text[pos:end]
        if line.strip(" \t") == "":
            if current is not None:
                blocks.append(tuple(current))
            current = None
        else:
            marker = _MARKER.match(line)
            if marker:
                if current is not None:
                    blocks.append(tuple(current))
                current = [pos + marker.end(), end]
            elif current is None:
                current = [pos, end]
            else:
                current[1] = end
        if newline < 0:
            break
        pos = newline + 1
    if current is not None:
        blocks.append(tuple(current))
    return blocks


def _has_letter_or_digit(text):
    for ch in text:
        category = unicodedata.category(ch)
        if category[0] == "L" or category == "Nd":
            return True
    return False


def _sentences(text, start, end):
    """The checked sentences of one block, as trimmed (start, end) pairs of the joined text."""
    block = text[start:end]
    cuts = _sentence_ends(block)
    if not cuts or cuts[-1] != len(block):
        cuts.append(len(block))
    found = []
    previous = 0
    for cut in cuts:
        a = previous
        b = cut
        previous = cut
        while a < b and block[a].isspace():
            a += 1
        while b > a and block[b - 1].isspace():
            b -= 1
        if a < b and _has_letter_or_digit(block[a:b]):
            found.append((start + a, start + b))
    return found


class _Used(object):
    """What one file produced: sentences checked, sentences not approved, findings, entries used."""

    def __init__(self):
        self.checked = 0
        self.failed = 0
        self.findings = []
        self.used = set()


def _check_text(text, by_sentence, longest, most_stops):
    work, spans = _working(text)
    joined, joined_spans = _keep_hyphen(work, spans)
    starts = _line_starts(text)
    result = _Used()
    for block_start, block_end in _blocks(joined):
        sentences = _sentences(joined, block_start, block_end)
        result.checked += len(sentences)
        i = 0
        while i < len(sentences):
            first = sentences[i][0]
            source_start = joined_spans[first][0]
            line = bisect.bisect_right(starts, source_start)
            covered = None
            # A run of k + 1 sentences holds at least k of the characters . ! and ?,
            # so no entry covers a longer run.
            for j in range(i, min(len(sentences), i + most_stops + 1)):
                source_end = joined_spans[sentences[j][1] - 1][1]
                prepared = prepare(text[source_start:source_end])
                if len(prepared) > longest:
                    break
                if prepared in by_sentence:
                    covered = (j, by_sentence[prepared])
            if covered is None:
                result.failed += 1
                result.findings.append(
                    (line, "unlisted", _shown(text, source_start,
                                              joined_spans[sentences[i][1] - 1][1])))
                i += 1
                continue
            j, (number, status) = covered
            if status == "approved":
                result.used.add(number)
            else:
                result.failed += j - i + 1
                result.findings.append(
                    (line, "%s, entry #%d" % (status, number),
                     _shown(text, source_start, joined_spans[sentences[j][1] - 1][1])))
            i = j + 1
    return result


def _shown(text, start, end):
    """A run as it stands in the file: whitespace runs as one space, escaped like a path."""
    return printed_path(" ".join(text[start:end].split()))


# ---------------------------------------------------------------- the run

def _check_file(path, by_sentence, longest, controls, most_stops):
    label = printed_path(path)
    try:
        text = _read_text(path, False)
        found = _check_text(text, by_sentence, longest, most_stops)
    except _Dead as dead:
        return "DEAD", ["DEAD  %s: %s" % (label, dead.args[0])], set()
    except Exception:
        return "DEAD", ["DEAD  %s: cannot read" % label], set()
    prepared_text = _squash(text)
    if not any(control in prepared_text for control in controls):
        return "DEAD", ["DEAD  %s: control not found" % label], set()
    if found.checked == 0:
        return "DEAD", ["DEAD  %s: no checked sentence" % label], set()
    if not found.findings:
        return "OK", ["OK    %s: %d sentences, all approved (control found)"
                      % (label, found.checked)], found.used
    out = ["FAIL  %s: %d of %d sentences not approved" % (label, found.failed, found.checked)]
    for line, kind, shown in found.findings:
        out.append("%s:%d: %s: %s" % (label, line, kind, shown))
    return "FAIL", out, found.used


def run(*, list_path, files, controls, stale_check=False, check_sources=False):
    try:
        return _run(list_path, list(files), list(controls), stale_check, check_sources)
    except Exception:
        return _cannot("internal error")


_QUOTE_FOUND = "found"
_QUOTE_NOT_FOUND = "not found"
_QUOTE_UNREADABLE = "unreadable"
_QUOTE_UNVERIFIED = "unverified"


def _check_one_source(list_path, source, quote):
    """(result, reason) for one quote: found, not found, unreadable with a reason, or unverified.

    The source is a path relative to the list's folder. A source that is not there at all (a
    URL, a record id, a missing path) is unverified and nothing is read."""
    # quote_check imports this module, so it is imported here, when a run needs it.
    from career_track_record import quote_check
    resolved = os.path.join(os.path.dirname(list_path), source)
    if not os.path.lexists(resolved):
        return _QUOTE_UNVERIFIED, ""
    status, reason = quote_check.check_quote(quote, resolved)
    if status == quote_check.FOUND:
        return _QUOTE_FOUND, ""
    if status == quote_check.NOT_FOUND:
        return _QUOTE_NOT_FOUND, ""
    return _QUOTE_UNREADABLE, reason


def _check_sources(list_path, quotes):
    """The source lines, the two count lines, and what the quotes do to the exit status.

    Lines name an entry only by its number; no quote, source or source text is printed.
    Refused entries are never checked. A proposed entry, and an unverified quote, never change
    the exit status."""
    lines = []
    counts = {"approved": [0, 0, 0, 0], "proposed": [0, 0, 0, 0]}
    order = (_QUOTE_FOUND, _QUOTE_NOT_FOUND, _QUOTE_UNREADABLE, _QUOTE_UNVERIFIED)
    least = 0
    for number, status, source, quote in quotes:
        if status not in counts:
            continue
        result, reason = _check_one_source(list_path, source, quote)
        counts[status][order.index(result)] += 1
        if result == _QUOTE_NOT_FOUND:
            lines.append("%s, entry #%d: quote not found" % (status, number))
            if status == "approved":
                least = max(least, 1)
        elif result == _QUOTE_UNREADABLE:
            lines.append("%s, entry #%d: source unreadable (%s)" % (status, number, reason))
            if status == "approved":
                least = 2
        elif result == _QUOTE_UNVERIFIED:
            lines.append("%s, entry #%d: source unverified" % (status, number))
    for status in ("approved", "proposed"):
        lines.append("quotes, %s: %d found, %d not found, %d unreadable, %d unverified"
                     % ((status,) + tuple(counts[status])))
    return lines, least


def _run(list_path, files, controls, stale_check, check_sources):
    if not files:
        return _cannot("no input file")
    if not controls:
        return _cannot("no --control given")
    prepared_controls = [c for c in (prepare_control(c) for c in controls) if c != ""]
    if not prepared_controls:
        return _cannot("no usable --control given")
    if not list_path:
        return _cannot("no list (give --list)")
    try:
        entries, quotes = _read_list(list_path)
    except ListError as exc:
        return _cannot(str(exc))
    by_sentence = dict((prepared, (number, status)) for number, status, prepared in entries)
    longest = max([len(prepared) for _n, _s, prepared in entries] or [0])
    most_stops = max([sum(prepared.count(c) for c in ".!?") for _n, _s, prepared in entries]
                     or [0])
    lines = []
    kinds = set()
    used = set()
    for position, path in enumerate(files, 1):
        if _is_the_list(path, list_path):
            kinds.add("DEAD")
            lines.append("DEAD  file #%d: is the list" % position)
            continue
        kind, out, used_here = _check_file(path, by_sentence, longest, prepared_controls,
                                           most_stops)
        kinds.add(kind)
        lines.extend(out)
        used |= used_here
    stale = 0
    if stale_check and "DEAD" not in kinds:
        for number, status, _prepared in entries:
            if status == "approved" and number not in used:
                lines.append("stale entry #%d" % number)
                stale += 1
    if "DEAD" in kinds:
        code = 2
    elif "FAIL" in kinds or stale:
        code = 1
    else:
        code = 0
    if check_sources:
        source_lines, least = _check_sources(list_path, quotes)
        lines.extend(source_lines)
        code = max(code, least)
    return barred.Result(code, True, text="".join(line + "\n" for line in lines))
