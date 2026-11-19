"""The versioned draft file: ``track-record drafts check`` and ``track-record drafts extract``.

A document such as a cover letter goes through many versions. This module reads the one file
that holds them, checks it against the rules of the spec, and can write out one version's text.
Behaviour: docs/specs/drafts.md.

Output names only the file's path, ids, line numbers and counts. It never holds a version's
text, a change note or a result note. The module starts no program, never writes to the draft
file, and writes only the new file ``OUT`` that ``extract`` is given.
"""

import hashlib
import os
import re

from career_track_record import barred, reader_harness, record_check

BOM = b"\xef\xbb\xbf"

_BREAK = re.compile(r"\r\n|\r|\n")
_LINE_BREAK = re.compile(rb"\r\n|\r|\n")
_HEADER = re.compile(r"## (v(?:0|[1-9][0-9]*)|result|send)")

# The keys of each kind of section, in file order, and the ones that may be left out.
_ORDER = {
    "version": ("parent", "date", "change", "sha256"),
    "result": ("version", "date", "run", "note"),
    "send": ("version", "date"),
}
_OPTIONAL = {"version": ("sha256",), "result": ("note",), "send": ()}

NO_EARLIER = "no earlier copy given"
NO_EARLIER_LINE = "no earlier copy given: rule 8 not applied"


def _shown(text):
    return barred.printed_path(text)


# ------------------------------------------------------------------ lines

def split_lines(text):
    """The lines of a text. Only LF, CRLF and a lone CR end a line, and a final line break
    starts no line."""
    lines = _BREAK.split(text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def is_blank(line):
    """True for a line that is empty or holds only spaces and tabs."""
    return line.strip(" \t") == ""


# ------------------------------------------------------------------ sections

class Section(object):
    """One section of the file. ``header`` is the line of its header line; ``body`` holds
    (line, text) for every line up to the next header line. ``fault`` is the one rule 1
    finding (line, text) of a section that does not follow the form, else None; ``keys`` maps
    each key of an accepted section to (line, value)."""

    def __init__(self, kind, ident, header):
        self.kind = kind
        self.ident = ident
        self.header = header
        self.body = []
        self.fault = None
        self.keys = {}
        self.text_lines = []

    def digits(self):
        """The order of a version's number: a longer run of digits is the larger number,
        because no id has a leading zero."""
        return (len(self.ident) - 1, self.ident[1:])


class Draft(object):
    def __init__(self, sections, before):
        self.sections = sections
        self.before = before

    def accepted(self):
        return [section for section in self.sections if section.fault is None]


def _key_index(line, order):
    for index, key in enumerate(order):
        if line.startswith(key + ": "):
            return index
    return None


def _form(section):
    """The faults 1.1 to 1.6 of spec section 4 that a section has, as (line, number, text) in
    the order they were found."""
    order = _ORDER[section.kind]
    body = section.body
    found = []
    if section.kind == "version":
        stop = None
        for position, (_number, line) in enumerate(body):
            if line == "text:":
                stop = position
                break
        region = body if stop is None else body[:stop]
    else:
        stop = None
        region = []
        for item in body:
            if is_blank(item[1]):
                break
            region.append(item)
    first = order[0]
    if not region or not region[0][1].startswith(first + ": "):
        found.append((section.header, 1, "no %s line after the header" % first))
    last = -1
    present = set()
    keys = {}
    for number, line in region:
        index = _key_index(line, order)
        if index is None:
            found.append((number, 2, "unknown key"))
            continue
        present.add(order[index])
        if index <= last:
            found.append((number, 3, "key out of order"))
            continue
        last = index
        keys[order[index]] = (number, line[len(order[index]) + 2:])
    if section.kind == "version":
        if stop is not None:
            present.add("text")
        required = [key for key in order if key not in _OPTIONAL["version"]] + ["text"]
    else:
        required = [key for key in order if key not in _OPTIONAL[section.kind]]
    for key in required:
        if key not in present:
            found.append((section.header, 4, "no %s line" % key))
    if section.kind == "version":
        if stop is not None:
            section.text_lines = [line for _number, line in body[stop + 1:]]
            if all(is_blank(line) for line in section.text_lines):
                found.append((section.header, 5, "empty text"))
    else:
        for number, line in body[len(region):]:
            if not is_blank(line):
                found.append((number, 6, "line after an entry"))
                break
    section.keys = keys
    return found


def read_draft(lines):
    """The Draft that a list of lines makes: its sections, each judged by rule 1, and the
    lines that are not blank before the first header."""
    sections = []
    before = []
    for number, line in enumerate(lines, 1):
        match = _HEADER.fullmatch(line)
        if match:
            word = match.group(1)
            kind = "version" if word.startswith("v") else word
            sections.append(Section(kind, word if kind == "version" else None, number))
        elif sections:
            sections[-1].body.append((number, line))
        elif not is_blank(line):
            before.append((number, line))
    for section in sections:
        found = _form(section)
        if found:
            best = min(found, key=lambda item: (item[0], item[1]))
            section.fault = (best[0], best[2])
            section.keys = {}
    return Draft(sections, before)


# ------------------------------------------------------------------ the version's bytes

def version_bytes(section):
    """The bytes that a version's sha256 is taken over (spec 3.2): each line of its text, once
    the blank lines at the end are dropped, followed by one line feed."""
    lines = list(section.text_lines)
    while lines and is_blank(lines[-1]):
        lines.pop()
    return "".join(line + "\n" for line in lines).encode("utf-8")


def _digest(section):
    return hashlib.sha256(version_bytes(section)).hexdigest()


# ------------------------------------------------------------------ the rules

def rule_1(draft):
    """Form. Each finding is (line, text)."""
    found = [(number, "line before the first section") for number, _line in draft.before]
    found += [section.fault for section in draft.sections if section.fault is not None]
    return found


def rule_2(accepted):
    """Ids are unique and increase in file order."""
    found = []
    first = {}
    previous = None
    for section in accepted:
        if section.kind != "version":
            continue
        if section.ident in first:
            found.append((section.header,
                          "repeated id, first on line %d" % first[section.ident]))
        else:
            first[section.ident] = section.header
            if previous is not None and section.digits() < previous.digits():
                found.append((section.header, "id out of order, line %d" % previous.header))
        previous = section
    return found


def rule_3(accepted):
    """Parents, and the versions that entries name."""
    where = {}
    for position, section in enumerate(accepted):
        if section.kind == "version" and section.ident not in where:
            where[section.ident] = position
    found = []
    first_version = True
    for position, section in enumerate(accepted):
        if section.kind == "version":
            line, value = section.keys["parent"]
            if first_version:
                first_version = False
                if value != "none":
                    found.append((line, "first version has a parent"))
                continue
            if value == "none":
                continue
            if value == section.ident:
                found.append((line, "parent is itself"))
                continue
        elif section.kind in ("result", "send"):
            line, value = section.keys["version"]
        else:
            continue
        place = where.get(value)
        if place is not None and place < position:
            continue
        if place is not None and place > position:
            noun = "parent" if section.kind == "version" else "version"
            found.append((line, "%s comes later, line %d" % (noun, accepted[place].header)))
        elif section.kind == "version":
            found.append((line, "parent not found"))
        else:
            found.append((line, "version not found"))
    return found


def rule_4(accepted):
    """Each version has a change note."""
    return [(section.keys["change"][0], "empty change note")
            for section in accepted
            if section.kind == "version" and is_blank(section.keys["change"][1])]


def rule_5(accepted):
    """Each section's date is a real day, and none is earlier than the section before it."""
    found = []
    previous = None
    for section in accepted:
        line, value = section.keys["date"]
        day = record_check.real_date(value)
        if day is None:
            found.append((line, "not a date"))
        elif previous is not None:
            before = record_check.real_date(previous.keys["date"][1])
            if before is None:
                found.append((line, "dates cannot be compared, line %d" % previous.header))
            elif day < before:
                found.append((line, "dated before the section on line %d" % previous.header))
        previous = section
    return found


def rule_6(accepted):
    """There is at most one send entry."""
    found = []
    first = None
    for section in accepted:
        if section.kind != "send":
            continue
        if first is None:
            first = section.header
        else:
            found.append((section.header, "a second send entry, first on line %d" % first))
    return found


def rule_7(accepted):
    """A sha256 line equals the version's sha256."""
    return [(section.keys["sha256"][0], "sha256 does not match the text")
            for section in accepted
            if section.kind == "version" and "sha256" in section.keys
            and section.keys["sha256"][1] != _digest(section)]


def rule_8(data, earlier):
    """The earlier copy is still the start of the file, byte for byte. A finding with no line
    is (None, text)."""
    common = min(len(data), len(earlier))
    if data[:common] != earlier[:common]:
        position = 0
        while data[position] == earlier[position]:
            position += 1
        breaks = len(_LINE_BREAK.findall(data[:position]))
        # A line feed that follows a carriage return is the second half of one line break.
        if data[position:position + 1] == b"\n" and data[:position].endswith(b"\r"):
            breaks -= 1
        return [(1 + breaks, "differs from the earlier copy")]
    if len(data) < len(earlier):
        return [(None, "shorter than the earlier copy")]
    return []


def rule_9(accepted, folder, lookup=os.path.isdir):
    """Each result entry's run folder exists. ``lookup`` says whether a path is a folder."""
    found = []
    for section in accepted:
        if section.kind != "result":
            continue
        line, run = section.keys["run"]
        if is_blank(run) or os.path.isabs(run) or not lookup(os.path.join(folder, run)):
            found.append((line, "run folder not found"))
    return found


# ------------------------------------------------------------------ the self-test

def _built(*parts):
    return "".join(parts)


def _version(ident, parent="none", date="2026-01-01", change="first", extra="",
             text="Words.\n"):
    return ("## %s\nparent: %s\ndate: %s\nchange: %s\n%stext:\n%s"
            % (ident, parent, date, change, extra, text))


def _entry(kind, ident, date="2026-01-01", extra=""):
    return "## %s\nversion: %s\ndate: %s\n%s" % (kind, ident, date, extra)


def _read(text):
    return read_draft(split_lines(text))


def _planted():
    """(rule, call, expected) for each planted fault. ``call`` looks the rule up when it runs,
    so a rule that is replaced is the one that is tested. Nothing here reads a file or looks
    up a path."""
    def accepted(text):
        return _read(text).accepted()

    def present(path):
        return os.path.basename(path) == "here"

    return [
        (1, lambda: rule_1(_read(_version("v1") + "## v2\nWords.\n")),
         [(7, "no parent line after the header")]),
        (2, lambda: rule_2(accepted(_version("v1") + _version("v1"))),
         [(7, "repeated id, first on line 1")]),
        (3, lambda: rule_3(accepted(_version("v1") + _version("v2", parent="v9"))),
         [(8, "parent not found")]),
        (4, lambda: rule_4(accepted(_version("v1", change=""))),
         [(4, "empty change note")]),
        (5, lambda: rule_5(accepted(_version("v1", date="2026-02-30"))),
         [(3, "not a date")]),
        (6, lambda: rule_6(accepted(_version("v1") + _entry("send", "v1")
                                    + _entry("send", "v1"))),
         [(10, "a second send entry, first on line 7")]),
        (7, lambda: rule_7(accepted(_version("v1", extra="sha256: " + "0" * 64 + "\n"))),
         [(5, "sha256 does not match the text")]),
        (8, lambda: rule_8(b"a\nb\nc\n", b"a\nB\n"),
         [(2, "differs from the earlier copy")]),
        (9, lambda: rule_9(accepted(_version("v1")
                                    + _entry("result", "v1", extra="run: runs/here\n")
                                    + _entry("result", "v1", extra="run: runs/gone\n")),
                           "folder", present),
         [(14, "run folder not found")]),
    ]


def _self_test():
    """The number of the first rule that does not report exactly its planted fault, or None."""
    for rule, call, expected in _planted():
        if call() != expected:
            return rule
    return None


# ------------------------------------------------------------------ the report

class Report(object):
    """What a check found. ``dead`` is the DEAD reason or None; ``by_rule`` maps each rule
    number to its findings; ``findings`` is every finding in line order; ``versions`` is the
    list of accepted versions."""

    def __init__(self):
        self.dead = None
        self.counts = ""
        self.earlier = NO_EARLIER
        self.send_copy = "none"
        self.by_rule = {}
        self.findings = []
        self.versions = []


def _counts(accepted, found3, found9):
    versions = [s for s in accepted if s.kind == "version"]
    results = [s for s in accepted if s.kind == "result"]
    sends = [s for s in accepted if s.kind == "send"]
    bad_parents = set(line for line, _text in found3)
    resolved = sum(1 for s in versions if s.keys["parent"][0] not in bad_parents)
    missing = set(line for line, _text in found9)
    found = sum(1 for s in results if s.keys["run"][0] not in missing)
    return ("versions %d, parents resolved %d, results %d, run folders found %d, "
            "send entries %d" % (len(versions), resolved, len(results), found, len(sends)))


def _same_file(first, second):
    try:
        return os.path.samefile(first, second)
    except (OSError, ValueError):
        return False


def _earlier_state(path, draft_path):
    """(bytes, None) for an earlier copy that can be compared, else (None, DEAD reason)."""
    data, code = record_check.read_source(path)
    if code == "missing":
        return None, "earlier copy not found"
    if code is not None:
        return None, "earlier copy cannot be read"
    if not data:
        return None, "earlier copy empty"
    if _same_file(path, draft_path):
        return None, "earlier copy is the draft file itself"
    return data, None


def build_report(data, draft_path, earlier=None, lookup=os.path.isdir):
    """The Report for a draft file's bytes (valid UTF-8) and the optional earlier copy's path."""
    body = data[len(BOM):] if data.startswith(BOM) else data
    report = Report()
    draft = _read(body.decode("utf-8"))
    accepted = draft.accepted()
    folder = os.path.dirname(draft_path)
    by_rule = {1: rule_1(draft), 2: rule_2(accepted), 3: rule_3(accepted),
               4: rule_4(accepted), 5: rule_5(accepted), 6: rule_6(accepted),
               7: rule_7(accepted), 8: [], 9: rule_9(accepted, folder, lookup)}
    report.counts = _counts(accepted, by_rule[3], by_rule[9])
    report.versions = [s for s in accepted if s.kind == "version"]
    for section in accepted:
        if section.kind == "send":
            report.send_copy = section.keys["version"][1]
            break
    if not body:
        report.dead = "empty file"
        return report
    if not report.versions:
        report.dead = "no version"
        return report
    if earlier is not None:
        old, reason = _earlier_state(earlier, draft_path)
        if reason is not None:
            report.dead = reason
            return report
        by_rule[8] = rule_8(data, old)
        report.earlier = "earlier copy %d bytes, file %d bytes" % (len(old), len(data))
    report.by_rule = by_rule
    merged = []
    for number in range(1, 10):
        merged += by_rule[number]
    merged.sort(key=lambda item: (item[0] is None, item[0] or 0))
    report.findings = merged
    return report


def finding_lines(shown, report):
    """The finding lines of a report, one per fault."""
    return ["%s: %s" % (shown, text) if line is None else "%s:%d: %s" % (shown, line, text)
            for line, text in report.findings]


def status_lines(shown, report):
    """The status line of spec section 6, then the finding lines of a check that FAILs."""
    if report.dead is not None:
        return ["DEAD  %s: %s; %s" % (shown, report.dead, report.counts)]
    if not report.findings:
        return ["OK    %s: %s; send copy %s; %s"
                % (shown, report.counts, report.send_copy, report.earlier)]
    head = ("FAIL  %s: %s; faults %d; %s"
            % (shown, report.counts, len(report.findings), report.earlier))
    return [head] + finding_lines(shown, report)


# ------------------------------------------------------------------ the run

def _cannot(reason):
    return reader_harness.Result(2, False, error="cannot run: %s" % reason)


def _exit_code(report):
    if report.dead is not None:
        return 2
    return 1 if report.findings else 0


def _load(path):
    """(bytes, None) of a draft file that can be read as UTF-8, else (None, the reason)."""
    name = _shown(os.path.basename(path.rstrip("/")) or path)
    reason = "cannot read the draft file: %s" % name
    data, code = record_check.read_source(path)
    if code is not None:
        return None, reason
    try:
        (data[len(BOM):] if data.startswith(BOM) else data).decode("utf-8")
    except UnicodeDecodeError:
        return None, reason
    return data, None


def check(path, earlier=None):
    failed = _self_test()
    if failed is not None:
        return _cannot("self-test failed: rule %d" % failed)
    data, reason = _load(path)
    if reason is not None:
        return _cannot(reason)
    report = build_report(data, path, earlier)
    lines = status_lines(_shown(path), report)
    return reader_harness.Result(_exit_code(report), True, text="\n".join(lines) + "\n")


def _discard(_text):
    return None


def _write_new(out, data):
    """Create ``out`` and write ``data`` to it. True when it was written; on any failure the
    file this call created is removed and the result is False."""
    created = False
    descriptor = None
    try:
        descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, "O_NOFOLLOW", 0), 0o666)
        created = True
        view = memoryview(data)
        while len(view):
            view = view[os.write(descriptor, view):]
        os.close(descriptor)
        descriptor = None
        return True
    except (OSError, ValueError):
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if created:
            try:
                os.unlink(out)
            except OSError:
                pass
        return False


def _exists(path):
    try:
        return os.path.lexists(path)
    except ValueError:
        return False


def extract(path, version_id, out, earlier=None, emit=_discard):
    """Check the draft file, then write version ``version_id``'s bytes to the new file ``out``.

    ``emit`` is called with the standard-error text, when there is any, before ``out`` is
    created; if it raises OSError nothing is written and the run cannot go ahead. The same text
    is in ``error`` of the Result that a run returns."""
    if _exists(out):
        return _cannot("--out names a path that already exists")
    failed = _self_test()
    if failed is not None:
        return _cannot("self-test failed: rule %d" % failed)
    data, reason = _load(path)
    if reason is not None:
        return _cannot(reason)
    report = build_report(data, path, earlier)
    shown = _shown(path)
    wanted = None
    if report.dead is None:
        for section in report.versions:
            if section.ident == version_id:
                wanted = section
                break
        if wanted is None:
            return _cannot("no version %s" % _shown(version_id))
    stop = report.dead is not None or any(report.by_rule[n] for n in range(1, 9))
    if stop:
        lines = status_lines(shown, report)
        code = _exit_code(report)
    else:
        lines = ["%s:%d: %s" % (shown, line, text) for line, text in report.by_rule[9]]
        if earlier is None:
            lines.append(NO_EARLIER_LINE)
        code = 0
    text = "".join(line + "\n" for line in lines)
    if text:
        try:
            emit(text)
        except OSError:
            return _cannot("cannot write output")
    if stop:
        return reader_harness.Result(code, True, error=text)
    if not _write_new(out, version_bytes(wanted)):
        return _cannot("cannot write output")
    return reader_harness.Result(0, True, error=text)
