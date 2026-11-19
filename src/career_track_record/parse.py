"""Parse check: what a program that reads a PDF's text gets from a resume PDF.

The behaviour is stated in docs/specs/parse.md (spec 1). In short: read the PDF's default
text (and its layout text, for the wrapped-compound check), and report whether each page
holds text, where the name and contact details are, which common English section headings
can be seen, how many date formats the date ranges use, and whether a hyphenated word is
split across two lines. A file is DEAD, never OK, when it could not be checked.

``check_text`` is the pure function; ``check_file`` reads one PDF and calls it; ``run``
checks the options and prints the blocks. The name and contacts are the user's own
arguments at run time: they are never shipped and never written anywhere.
"""

import collections
import os
import re
import unicodedata

from career_track_record import barred, pdf_text, wrapped_compounds

FAMILIES = ("experience", "education", "skills", "summary", "projects", "certifications")
DEFAULT_SECTIONS = ("experience", "skills")
DEFAULT_MIN_PAGE_CHARS = 20
_BOM = chr(0xFEFF)

# The seam that locates the shipped list of section headings (as tone.py locates its rules).
_SECTION_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "data", "section-names.txt")

NO_TEXT = ("no text; the PDF holds no selectable text (a scan?), so export it again from "
           "the document")
NAME_NOT_FOUND = ("name not found; check that the name you gave matches the PDF, and that "
                  "its text can be selected")
FAIL_TAIL = ("fix them in the document the PDF was made from, make the PDF again, and run "
             "this again")
FAMILIES_LINE = "families: " + ", ".join(FAMILIES)


class ListError(Exception):
    """The shipped section list is missing or damaged."""


class _Dead(Exception):
    pass


# ---------------------------------------------------------------- the section list

def load_headings(path=None):
    """The shipped list as a dict of folded heading -> family, in the order of the file.

    Raises ListError for a missing file, a byte-order mark, a line with no tab, an unknown
    family, an empty heading, or a file with no entry."""
    if path is None:
        path = _SECTION_LIST
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        text = data.decode("utf-8")
    except (OSError, ValueError):
        raise ListError("unreadable")
    if text.startswith(_BOM):
        raise ListError("byte-order mark")
    headings = collections.OrderedDict()
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.strip() == "" or line.startswith("#"):
            continue
        family, tab, heading = line.partition("\t")
        if not tab or family not in FAMILIES:
            raise ListError("bad line")
        heading = barred.prepare(heading)
        if heading == "":
            raise ListError("empty heading")
        headings.setdefault(heading, family)
    if not headings:
        raise ListError("no entry")
    return headings


# ---------------------------------------------------------------- matching name and contacts

def _occurs(needle, hay):
    """True when ``needle`` is in ``hay`` with a boundary character (or the end) on each side."""
    if needle == "":
        return False
    start = 0
    while True:
        index = hay.find(needle, start)
        if index < 0:
            return False
        before = hay[index - 1] if index > 0 else None
        end = index + len(needle)
        after = hay[end] if end < len(hay) else None
        if ((before is None or barred._is_boundary(before))
                and (after is None or barred._is_boundary(after))):
            return True
        start = index + 1


def _first_page(needle, prepared_pages):
    for number, page in enumerate(prepared_pages, 1):
        if _occurs(needle, page):
            return number
    return None


# ---------------------------------------------------------------- date ranges

_SEPARATORS = "-" + chr(0x2013) + chr(0x2014)
_CLASSES = ("MM/DD/YYYY", "MM/YYYY", "YYYY-MM", "Mon YYYY", "YYYY")
_YEAR = r"(?:19|20)[0-9][0-9]"
_MONTH = r"(?:0?[1-9]|1[0-2])"
_DAY = r"(?:0?[1-9]|[12][0-9]|3[01])"
_MONTH_NAMES = ("january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|"
                "august|aug|september|sept|sep|october|oct|november|nov|december|dec")
_DATE_FORMS = [
    re.compile(_MONTH + "/" + _DAY + "/" + _YEAR),
    re.compile(_MONTH + "/" + _YEAR),
    re.compile(_YEAR + "-(?:0[1-9]|1[0-2])"),
    re.compile("(?:" + _MONTH_NAMES + r")\.?[ \t]+" + _YEAR),
    re.compile(_YEAR),
]


def _touching(ch):
    """True for a character a date must not touch: a letter, a digit or a slash."""
    category = unicodedata.category(ch)
    return ch == "/" or category[0] == "L" or category == "Nd"


def _date_at(line, pos):
    """(class, end) of the date that starts at ``pos``, or None. Longest class first."""
    if pos > 0 and _touching(line[pos - 1]):
        return None
    for form, label in zip(_DATE_FORMS, _CLASSES):
        match = form.match(line, pos)
        if match and not (match.end() < len(line) and _touching(line[match.end()])):
            return label, match.end()
    return None


def _skip_blanks(line, pos):
    while pos < len(line) and line[pos] in " \t":
        pos += 1
    return pos


def _open_end(line, pos):
    """The end of ``present`` or ``current`` at ``pos`` when no letter or digit follows."""
    for word in ("present", "current"):
        end = pos + len(word)
        if line.startswith(word, pos) and not (end < len(line) and unicodedata.category(
                line[end])[0] in ("L", "N")):
            return end
    return None


def _range_dates(line):
    """The classes of the dates in each range on one case-folded line, left to right."""
    found = []
    pos = 0
    while pos < len(line):
        first = _date_at(line, pos)
        if first is not None:
            label, end = first
            at = _skip_blanks(line, end)
            after = None
            if at < len(line) and line[at] in _SEPARATORS:
                after = at + 1
            elif line.startswith("to", at) and at > end and line[at + 2:at + 3] in (" ", "\t"):
                after = at + 2
            if after is not None:
                after = _skip_blanks(line, after)
                second = _date_at(line, after)
                if second is not None:
                    found.extend([label, second[0]])
                    pos = second[1]
                    continue
                stop = _open_end(line, after)
                if stop is not None:
                    found.append(label)
                    pos = stop
                    continue
        pos += 1
    return found


def _dates_line(pages):
    counts = collections.Counter()
    for page in pages:
        for line in wrapped_compounds._lines(page):
            counts.update(_range_dates(line.casefold()))
    if not counts:
        return "  dates: no date ranges found", 0
    order = sorted(counts, key=lambda label: (-counts[label], _CLASSES.index(label)))
    word = "format" if len(order) == 1 else "formats"
    return ("  dates: %d %s (%s)" % (len(order), word, ", ".join(
        "%s %d" % (label, counts[label]) for label in order)), 1 if len(order) > 1 else 0)


# ---------------------------------------------------------------- one text

def _letters_and_digits(page):
    return sum(1 for ch in page
               if unicodedata.category(ch)[0] == "L" or unicodedata.category(ch) == "Nd")


def _plural(count, word):
    return "%d %s" % (count, word if count == 1 else word + "s")


def _section_lines(pages, headings, required):
    """The ``sections:`` line, and the number of missing required families."""
    first = {}
    for number, page in enumerate(pages, 1):
        for index, line in enumerate(wrapped_compounds._lines(page), 1):
            key = barred.prepare(line)
            if key.endswith(":"):
                key = key[:-1]
            family = headings.get(key)
            if family is not None and family not in first:
                first[family] = (number, index, line.strip())
    order = list(collections.OrderedDict.fromkeys(headings.values()))
    order += [family for family in FAMILIES if family not in order]
    wanted = set(required)

    def item(family):
        if family not in first:
            return "%s missing" % family
        number, index, text = first[family]
        return "%s found (page %d line %d: %s)" % (
            family, number, index, barred.printed_path(text))

    shown = [item(family) for family in order if family in wanted]
    shown += [item(family) for family in order if family in first and family not in wanted]
    missing = sum(1 for family in order if family in wanted and family not in first)
    return "  sections:" + (" " + ", ".join(shown) if shown else ""), missing


def _check(path, default_raw, get_layout, name, contacts, sections, min_page_chars, headings):
    shown_path = barred.printed_path(path)
    default = wrapped_compounds._normalise(default_raw)
    pages = wrapped_compounds._pages(default)
    counts = [_letters_and_digits(page) for page in pages]
    with_text = sum(1 for count in counts if count >= min_page_chars)
    body = ["  text: %s, %d with text" % (_plural(len(pages), "page"), with_text)]
    for number, count in enumerate(counts, 1):
        if count < min_page_chars:
            body.append("  page %d: little or no text (%d letters or digits)" % (
                number, count))
    findings = sum(1 for count in counts if count < min_page_chars)

    def dead(reason):
        return "DEAD", ["DEAD  %s: %s" % (shown_path, reason)] + body

    if not any(count > 0 for count in counts):
        return dead(NO_TEXT)
    try:
        layout_raw = get_layout()
    except _Dead as reason:
        return dead(reason.args[0])
    try:
        hits = wrapped_compounds.find_wrapped_compounds(default_raw, layout_raw)
    except wrapped_compounds.Dead as reason:
        return dead(reason.reason)

    prepared = [barred.prepare(page) for page in pages]
    found = _first_page(barred.prepare(name), prepared)
    if found is None:
        return dead(NAME_NOT_FOUND)
    if found == 1:
        body.append("  name: page 1")
    else:
        body.append("  name: found on page %d, not page 1" % found)
        findings += 1
    for contact in contacts:
        page = _first_page(barred.prepare(contact), prepared)
        label = barred.printed_path(contact)
        if page == 1:
            body.append('  contact "%s": page 1' % label)
        elif page is None:
            body.append('  contact "%s": not found' % label)
            findings += 1
        else:
            body.append('  contact "%s": found on page %d, not page 1' % (label, page))
            findings += 1
    line, missing = _section_lines(pages, headings, sections)
    body.append(line)
    findings += missing
    line, extra = _dates_line(pages)
    body.append(line)
    findings += extra
    body.extend(wrapped_compounds.hit_line(hit) for hit in hits)
    if not hits:
        body.append("  wrapped compounds: none")
    findings += sum(1 for hit in hits if hit.marker == wrapped_compounds.FINDING)
    if findings == 0:
        return "OK", ["OK    %s" % shown_path] + body
    return "FAIL", ["FAIL  %s: %s; %s" % (shown_path, _plural(findings, "finding"),
                                           FAIL_TAIL)] + body


def check_text(default_raw, layout_raw, name, contacts, sections, min_page_chars,
               path="x.pdf", headings=None):
    """Check the two raw texts of one file. Returns (status, lines) with status one of
    ``OK``, ``FAIL`` or ``DEAD`` and ``lines[0]`` the status line. ``sections`` is the list
    of required family names; ``headings`` is the loaded list (the shipped one if None)."""
    if headings is None:
        headings = load_headings()
    return _check(path, default_raw, lambda: layout_raw, name, list(contacts),
                  list(sections), min_page_chars, headings)


# ---------------------------------------------------------------- one file

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
    except Exception:
        raise _Dead("cannot read")


def check_file(path, name, contacts, sections, min_page_chars, headings=None):
    """Read one PDF and check it. Returns (status, lines) as ``check_text`` does."""
    if headings is None:
        headings = load_headings()
    try:
        if not path.lower().endswith(".pdf"):
            raise _Dead("not a PDF; give the PDF file")
        default_raw = _read(path, False)
    except _Dead as reason:
        return "DEAD", ["DEAD  %s: %s" % (barred.printed_path(path), reason.args[0])]
    return _check(path, default_raw, lambda: _read(path, True), name, list(contacts),
                  list(sections), min_page_chars, headings)


# ---------------------------------------------------------------- the run

def _cannot(message):
    return barred.Result(2, False, text="", error="cannot run: " + message)


def run(*, files, name, contacts, sections, min_page_chars):
    """Check the options (usage errors 4 to 9 of the spec, in order), then every file.

    ``name`` is the given text or None; ``sections`` and ``min_page_chars`` are the given
    text or None for the default."""
    try:
        return _run(list(files), name, list(contacts), sections, min_page_chars)
    except Exception:
        return _cannot("internal error")


def _run(files, name, contacts, sections, min_page_chars):
    if not files:
        return _cannot("no input file")
    if name is None:
        return _cannot("give --name, your name as it appears in the PDF")
    if barred.prepare(name) == "":
        return _cannot("--name is empty")
    if any(barred.prepare(contact) == "" for contact in contacts):
        return _cannot("--contact is empty")
    minimum = DEFAULT_MIN_PAGE_CHARS
    if min_page_chars is not None:
        significant = min_page_chars.lstrip("0")
        if (not re.fullmatch(r"[0-9]+", min_page_chars) or significant == ""
                or len(significant) > 18):
            return _cannot("--min-page-chars takes a whole number of 1 or more")
        minimum = int(significant)
    required = list(DEFAULT_SECTIONS)
    if sections is not None:
        required = []
        for item in sections.split(","):
            family = barred.prepare(item)
            if family == "":
                return _cannot("--sections: empty family name")
            if family not in FAMILIES:
                return _cannot("--sections: unknown family %s; %s" % (
                    barred.printed_path(family), FAMILIES_LINE))
            if family not in required:
                required.append(family)
    try:
        headings = load_headings()
    except ListError:
        return _cannot("the shipped section list is missing or damaged; reinstall")
    out = []
    kinds = set()
    for path in files:
        kind, lines = check_file(path, name, contacts, required, minimum, headings)
        kinds.add(kind)
        out.extend(lines)
    code = 2 if "DEAD" in kinds else (1 if "FAIL" in kinds else 0)
    return barred.Result(code, True, text="".join(line + "\n" for line in out))
