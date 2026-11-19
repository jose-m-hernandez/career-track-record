"""Wrapped-compound check: hyphenated words split across two lines in a PDF.

The behaviour is stated in docs/specs/wrapped-compounds.md. In short: read the PDF's
layout text and its default text, find each line that ends in a hyphen inside a word, and
report whether the default text joined the two halves into one word ("wellknown"). A file
is called OK only when both texts were read and one control string was found.

``find_wrapped_compounds(default_raw, layout_raw)`` is the pure function; ``run`` reads
the files and prints the status lines. Unlike barred, hit lines quote words from the
user's own file (the compound and the joined token).
"""

import re
import typing
import unicodedata

from career_track_record import barred, pdf_text

_LINE_BREAK = re.compile(r"\r\n|\r|\n")

FINDING = "finding"
NOTE = "note"
NOJOIN = "nojoin"


class Hit(typing.NamedTuple):
    """One wrap line: its page and line, the compound as printed, the joined token (or
    None) and one marker of ``finding``, ``note`` or ``nojoin`` (spec section 6)."""

    page: int
    line: int
    compound: str
    token: typing.Optional[str]
    marker: str


class Dead(Exception):
    """The texts cannot be checked. ``reason`` is the words that follow ``DEAD  <path>: ``."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


# ---------------------------------------------------------------- preparing the texts

def _normalise(text):
    """Step 1: NFKC, then remove every format character (Cf). Case is kept."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def _pages(text):
    """Step 2: split at each form feed; drop the one empty segment after the last."""
    pages = text.split("\f")
    if len(pages) > 1 and pages[-1] == "":
        pages.pop()
    return pages


def _lines(page):
    """Step 3: LF, CRLF and a lone CR end a line. Nothing else does (never splitlines)."""
    return _LINE_BREAK.split(page)


def _has_letter_or_digit(text):
    """True when the text holds a character of category L or Nd."""
    return any(unicodedata.category(ch)[0] == "L" or unicodedata.category(ch) == "Nd"
               for ch in text)


# ---------------------------------------------------------------- letters and word runs

def _letter_flags(text):
    """For each character: is it a letter (category L, or M right after a letter)?"""
    flags = []
    previous = False
    for ch in text:
        category = unicodedata.category(ch)
        letter = category[0] == "L" or (category[0] == "M" and previous)
        flags.append(letter)
        previous = letter
    return flags


def _word_runs(text):
    """The word runs of a text: maximal runs of letters and hyphen-minus, leading and
    trailing hyphens excluded. Returns (start, end) pairs, in order."""
    flags = _letter_flags(text)
    runs = []
    start = None
    for index in range(len(text) + 1):
        inside = index < len(text) and (flags[index] or text[index] == "-")
        if inside and start is None:
            start = index
        elif not inside and start is not None:
            first, last = start, index
            while first < last and text[first] == "-":
                first += 1
            while last > first and text[last - 1] == "-":
                last -= 1
            if first < last:
                runs.append((first, last))
            start = None
    return runs


def _leading_letters(text):
    """The maximal run of letters that begins ``text`` (possibly empty)."""
    flags = _letter_flags(text)
    end = 0
    while end < len(text) and flags[end]:
        end += 1
    return text[:end]


# ---------------------------------------------------------------- the wrap lines

def _wrap_hits(layout_page):
    """(line number, left half, right half) of each wrap line on one layout page."""
    lines = _lines(layout_page)
    found = []
    for index, line in enumerate(lines):
        body = line.rstrip()
        if len(body) < 2 or body[-1] != "-" or not _letter_flags(body[:-1])[-1]:
            continue
        following = None
        for later in lines[index + 1:]:
            if later.strip() != "":
                following = later.lstrip()
                break
        if following is None:
            continue
        right = _leading_letters(following)
        if right == "":
            continue
        before = body[:-1]
        runs = _word_runs(before)
        if not runs or runs[-1][1] != len(before):
            continue
        left = before[runs[-1][0]:]
        found.append((index + 1, left, right))
    return found


def _joins(token, left, right):
    prefix = left + (right[:3] if len(right) >= 3 else right)
    return token.casefold().startswith(prefix.casefold())


def find_wrapped_compounds(default_raw, layout_raw):
    """The hits of one file, in page and line order. Arguments: the default text first,
    then the layout text, both raw. Raises Dead for the reasons that arise here."""
    default = _normalise(default_raw)
    layout = _normalise(layout_raw)
    if not _has_letter_or_digit(default):
        raise Dead("no text; the PDF holds no selectable text (a scan?), so export it "
                   "again from the document")
    if not _has_letter_or_digit(layout):
        raise Dead("no layout text; export the PDF again")
    default_pages = _pages(default)
    layout_pages = _pages(layout)
    if len(default_pages) != len(layout_pages):
        raise Dead("page counts differ (default %d, layout %d); export the PDF again"
                   % (len(default_pages), len(layout_pages)))
    page_tokens = []
    for page in default_pages:
        page_tokens.append([page[a:b] for a, b in _word_runs(page)])
    joined = []
    for number, layout_page in enumerate(layout_pages, 1):
        taken = set()
        for line, left, right in _wrap_hits(layout_page):
            token = None
            for position, candidate in enumerate(page_tokens[number - 1]):
                if position not in taken and _joins(candidate, left, right):
                    taken.add(position)
                    token = candidate
                    break
            joined.append((number, line, left + "-" + right, token))
    every = [t.casefold() for tokens in page_tokens for t in tokens]
    hits = []
    for number, line, compound, token in joined:
        if token is None:
            marker = NOJOIN
        else:
            key = token.casefold()
            used = sum(1 for _n, _l, _c, other in joined
                       if other is not None and other.casefold() == key)
            unwrapped = every.count(key) > used
            written = compound.casefold() in every
            marker = NOTE if unwrapped and not written else FINDING
        hits.append(Hit(number, line, compound, token, marker))
    return hits


# ---------------------------------------------------------------- one file

class _Dead(Exception):
    pass


def _read(path, layout):
    try:
        with open(path, "rb"):
            pass
    except (OSError, ValueError):
        raise _Dead("cannot read")
    target = "./" + path if path.startswith("-") else path
    try:
        return pdf_text.pdf_text(target, layout=layout)
    except pdf_text.PdfTextError as exc:
        raise _Dead("pdftotext " + exc.reason)


def hit_line(hit):
    head = '  wrapped compounds: page %d line %d: "%s" is split across lines; ' % (
        hit.page, hit.line, hit.compound)
    if hit.marker == NOJOIN:
        return head + "extracted text does not join it (no join found, not a finding)"
    tail = 'extracted text reads "%s" ' % hit.token
    if hit.marker == NOTE:
        return head + tail + '(note: "%s" also appears unwrapped, nothing to fix)' % hit.token
    return head + tail + "(finding)"


def _check_file(path, controls):
    shown = barred.printed_path(path)
    try:
        if not path.lower().endswith(".pdf"):
            raise _Dead("not a PDF; give the PDF file")
        try:
            default_raw = _read(path, False)
            layout_raw = _read(path, True)
        except _Dead:
            raise
        except Exception:
            raise _Dead("cannot read")
        try:
            hits = find_wrapped_compounds(default_raw, layout_raw)
        except Dead as dead:
            raise _Dead(dead.reason)
        joined = " ".join(barred.fold(default_raw).split())
        if not any(control in joined for control in controls):
            raise _Dead("control not found; check that the text in the PDF can be selected")
    except _Dead as dead:
        return "DEAD", ["DEAD  %s: %s" % (shown, dead.args[0])]
    findings = sum(1 for hit in hits if hit.marker == FINDING)
    lines = [hit_line(hit) for hit in hits] or ["  wrapped compounds: none"]
    if findings == 0:
        return "OK", ["OK    %s: %d split compounds looked at, 0 findings (control found)"
                      % (shown, len(hits))] + lines
    return "FAIL", (["FAIL  %s: %d finding(s); lines marked \"finding\" need a fix, other "
                     "lines are for information" % (shown, findings)] + lines +
                    ["  next: reword or change the layout so the word does not break at "
                     "its hyphen, export the PDF again, and run this again"])


# ---------------------------------------------------------------- the run

def run(*, files, controls):
    try:
        return _run(list(files), list(controls))
    except Exception:
        return barred.Result(2, False, text="", error="cannot run: internal error")


def _cannot(message):
    return barred.Result(2, False, text="", error="cannot run: " + message)


def _run(files, controls):
    if not files:
        return _cannot("no input file")
    if not controls:
        return _cannot("no --control given")
    prepared = [c for c in (barred.prepare(c) for c in controls) if c != ""]
    if not prepared:
        return _cannot("no usable --control given")
    out = []
    kinds = set()
    for path in files:
        kind, lines = _check_file(path, prepared)
        kinds.add(kind)
        out.extend(lines)
    code = 2 if "DEAD" in kinds else (1 if "FAIL" in kinds else 0)
    return barred.Result(code, True, text="".join(line + "\n" for line in out))
