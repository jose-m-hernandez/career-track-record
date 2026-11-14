"""The record check: ``track-record record DECLARATION``.

A career record kept as tables is held together by references. This module reads a
declaration (the plan-file syntax of ``reader_harness``), reads the tables it names, and
reports each break by file and line. Behaviour: docs/specs/record-check.md.

Output names only declared tables, columns and paths, line numbers and counts. It never holds
a cell value. The module starts no program, writes no file, and reads only the declaration,
the tables and the earlier copies the declaration names.
"""

import csv
import datetime
import errno
import io
import os
import re
import stat
import sys

from career_track_record import barred, reader_harness

LIST_KEYS = ("tables", "references", "required", "values", "dates", "corrections", "earlier")

BOM = b"\xef\xbb\xbf"
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

_BREAK = re.compile(rb"\r\n|\r|\n")
_FILE_STATE = {"missing": "file missing", "irregular": "not a regular file",
               "unreadable": "cannot be read"}
_EARLIER_STATE = {"missing": "earlier copy missing",
                  "irregular": "earlier copy not a regular file",
                  "unreadable": "earlier copy cannot be read"}


def _shown(text):
    return barred.printed_path(text)


# ------------------------------------------------------------------ one check's answer

class Outcome(object):
    """What one check found. ``dead`` is the DEAD reason or None; ``counts`` is the text of
    the status line; ``findings`` is a list of (line, text), the line None for a finding that
    belongs to the whole file."""

    def __init__(self, dead=None, counts="", findings=None):
        self.dead = dead
        self.counts = counts
        self.findings = findings if findings is not None else []

    def key(self):
        return (self.dead, self.counts, [tuple(f) for f in self.findings])


def _dead(reason):
    return Outcome(dead=reason)


# ------------------------------------------------------------------ tables

class Table(object):
    """A table read from bytes. ``reason`` is why it cannot be used (a DEAD reason), else None.
    ``rows`` holds (line, fields) for every non-empty line after the header; ``whole`` and
    ``ragged`` split them by width."""

    def __init__(self, reason=None, header=None, rows=None):
        self.reason = reason
        self.header = header if header is not None else []
        self.rows = rows if rows is not None else []
        width = len(self.header)
        self.whole = [row for row in self.rows if len(row[1]) == width]
        self.ragged = [row for row in self.rows if len(row[1]) != width]


def read_source(path):
    """(bytes, None) for a regular file that was read, else (None, code) with the code one of
    missing, irregular and unreadable. The type is checked before anything opens the path, so
    a FIFO is never opened."""
    try:
        info = os.stat(path)
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ENOTDIR):
            return None, "missing"
        return None, "unreadable"
    except ValueError:
        return None, "unreadable"
    if not stat.S_ISREG(info.st_mode):
        return None, "irregular"
    try:
        with open(path, "rb") as handle:
            return handle.read(), None
    except (OSError, ValueError):
        return None, "unreadable"


def _csv_rows(text):
    """[(start line, fields)] of a CSV text, or None when it cannot be read as CSV. A field may
    be of any length: the module's limit is raised for this read and put back after it."""
    old_limit = csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        rows = []
        previous = 0
        while True:
            try:
                fields = next(reader)
            except StopIteration:
                return rows
            except csv.Error:
                return None
            rows.append((previous + 1, fields))
            previous = reader.line_num
    finally:
        csv.field_size_limit(old_limit)


def parse_table(data, fmt):
    """The Table that bytes make in format ``fmt`` (tsv or csv)."""
    if data.startswith(BOM):
        data = data[len(BOM):]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return Table("not UTF-8")
    if "\x00" in text:
        return Table("holds a NUL character")
    if text == "":
        return Table("empty file")
    if fmt == "csv":
        rows = _csv_rows(text)
        if rows is None:
            return Table("not readable as CSV")
        if rows[0][1] == []:
            return Table("no header")
        return Table(None, rows[0][1], [row for row in rows[1:] if row[1] != []])
    # A line break at the end of the file starts no row, because an empty line is never one.
    lines = reader_harness.LINE_BREAK.split(text)
    if lines[0] == "":
        return Table("no header")
    rows = [(number, line.split("\t")) for number, line in enumerate(lines, 1)
            if number > 1 and line != ""]
    return Table(None, lines[0].split("\t"), rows)


def load_table(path, fmt):
    """The Table in the file at ``path``; a file that cannot be used gives a DEAD reason."""
    data, code = read_source(path)
    if code is not None:
        return Table(_FILE_STATE[code])
    return parse_table(data, fmt)


def _column(table, name):
    """(index, None) for a column the header holds once, else (None, DEAD reason)."""
    count = table.header.count(name)
    if count == 0:
        return None, "no column %s" % _shown(name)
    if count > 1:
        return None, "column %s named twice" % _shown(name)
    return table.header.index(name), None


# ------------------------------------------------------------------ cell rules

def refs_single(cell):
    return [cell] if cell != "" else []


def refs_list(cell, characters):
    parts = [cell]
    for character in characters:
        parts = [piece for part in parts for piece in part.split(character)]
    parts = [part.strip(" ") for part in parts]
    return [part for part in parts if part != ""]


def refs_pattern(cell, regex):
    return [match.group(0) for match in regex.finditer(cell) if match.group(0) != ""]


def cell_references(cell, rule):
    """The references one cell holds under a rule: ("single",), ("list", characters) or
    ("pattern", compiled regex)."""
    if rule[0] == "single":
        return refs_single(cell)
    if rule[0] == "list":
        return refs_list(cell, rule[1])
    return refs_pattern(cell, rule[1])


# ------------------------------------------------------------------ the checks

def check_table(table, key):
    if table.reason is not None:
        return _dead(table.reason)
    index, reason = _column(table, key)
    if reason is not None:
        return _dead(reason)
    if not table.whole:
        return _dead("no whole rows")
    findings = []
    for number, fields in table.ragged:
        findings.append((number, "fields %d, the header has %d"
                         % (len(fields), len(table.header))))
    first = {}
    repeated = set()
    empty = repeats = 0
    for number, fields in table.whole:
        value = fields[index]
        if value == "":
            empty += 1
            findings.append((number, "empty key"))
        elif value in first:
            repeats += 1
            repeated.add(value)
            findings.append((number, "repeated key, first on line %d" % first[value]))
        else:
            first[value] = number
    findings.sort(key=lambda found: found[0])
    counts = ("whole rows %d, ragged rows %d, empty keys %d, repeats %d, keys with repeats %d"
              % (len(table.whole), len(table.ragged), empty, repeats, len(repeated)))
    return Outcome(None, counts, findings)


def check_references(table, column, target, target_name, target_column, rule):
    if table.reason is not None:
        return _dead(table.reason)
    if target.reason is not None:
        return _dead("target %s: %s" % (target_name, target.reason))
    index, reason = _column(table, column)
    if reason is not None:
        return _dead(reason)
    target_index, reason = _column(target, target_column)
    if reason is not None:
        return _dead("target %s: %s" % (target_name, reason))
    if not table.whole:
        return _dead("no whole rows")
    if not target.whole:
        return _dead("target %s: no whole rows" % target_name)
    known = set(fields[target_index] for _number, fields in target.whole)
    findings = []
    blank = total = dangling = 0
    distinct_dangling = set()
    for number, fields in table.whole:
        found = cell_references(fields[index], rule)
        if not found:
            blank += 1
            continue
        total += len(found)
        missing = [ref for ref in found if ref not in known]
        if missing:
            dangling += len(missing)
            distinct_dangling.update(missing)
            findings.append((number, "dangling %d" % len(missing)))
    if total == 0:
        return _dead("every cell blank")
    counts = ("whole rows %d, blank %d, references %d, dangling %d, "
              "rows with dangling %d, distinct dangling %d"
              % (len(table.whole), blank, total, dangling, len(findings),
                 len(distinct_dangling)))
    return Outcome(None, counts, findings)


def check_required(table, column):
    if table.reason is not None:
        return _dead(table.reason)
    index, reason = _column(table, column)
    if reason is not None:
        return _dead(reason)
    if not table.whole:
        return _dead("no whole rows")
    findings = [(number, "empty") for number, fields in table.whole
                if fields[index] == ""]
    counts = "whole rows %d, empty %d" % (len(table.whole), len(findings))
    return Outcome(None, counts, findings)


def check_values(table, column, allowed):
    if table.reason is not None:
        return _dead(table.reason)
    index, reason = _column(table, column)
    if reason is not None:
        return _dead(reason)
    if not table.whole:
        return _dead("no whole rows")
    filled = 0
    findings = []
    for number, fields in table.whole:
        cell = fields[index]
        if cell == "":
            continue
        filled += 1
        if cell not in allowed:
            findings.append((number, "outside the set"))
    if filled == 0:
        return _dead("no cell to check")
    counts = ("whole rows %d, filled %d, outside the set %d"
              % (len(table.whole), filled, len(findings)))
    return Outcome(None, counts, findings)


def real_date(cell):
    """The date a cell writes as YYYY-MM-DD, or None when it is not a date that exists."""
    if not DATE.fullmatch(cell):
        return None
    try:
        return datetime.date(int(cell[:4]), int(cell[5:7]), int(cell[8:]))
    except ValueError:
        return None


def check_dates(table, column):
    if table.reason is not None:
        return _dead(table.reason)
    index, reason = _column(table, column)
    if reason is not None:
        return _dead(reason)
    if not table.whole:
        return _dead("no whole rows")
    filled = 0
    findings = []
    for number, fields in table.whole:
        cell = fields[index]
        if cell == "":
            continue
        filled += 1
        if real_date(cell) is None:
            findings.append((number, "not a date"))
    if filled == 0:
        return _dead("no cell to check")
    counts = ("whole rows %d, filled %d, not a date %d"
              % (len(table.whole), filled, len(findings)))
    return Outcome(None, counts, findings)


def check_corrections(table, key, column, date_column):
    if table.reason is not None:
        return _dead(table.reason)
    key_index, reason = _column(table, key)
    if reason is not None:
        return _dead(reason)
    index, reason = _column(table, column)
    if reason is not None:
        return _dead(reason)
    date_index, reason = _column(table, date_column)
    if reason is not None:
        return _dead(reason)
    if not table.whole:
        return _dead("no whole rows")
    lines_of = {}
    for number, fields in table.whole:
        lines_of.setdefault(fields[key_index], []).append(number)
    fields_at = dict(table.whole)
    ragged_at = {}
    for number, fields in table.ragged:
        if key_index < len(fields):
            ragged_at.setdefault(fields[key_index], number)
    corrections = 0
    findings = []
    for number, fields in table.whole:
        target = fields[index]
        if target == "":
            continue
        corrections += 1
        if target == fields[key_index]:
            findings.append((number, "corrects itself"))
            continue
        lines = lines_of.get(target, [])
        if not lines and target in ragged_at:
            findings.append((number, "corrects a ragged row, line %d" % ragged_at[target]))
            continue
        if not lines:
            findings.append((number, "corrects a missing row"))
            continue
        if len(lines) > 1:
            findings.append((number, "corrects a key that is not unique"))
            continue
        corrected = lines[0]
        if corrected > number:
            findings.append((number, "corrects a later row, line %d" % corrected))
            continue
        then = real_date(fields[date_index])
        before = real_date(fields_at[corrected][date_index])
        if then is None or before is None:
            findings.append((number, "dates cannot be compared, line %d" % corrected))
        elif then < before:
            findings.append((number, "dated before the row it corrects, line %d" % corrected))
    if corrections == 0:
        return _dead("no correction rows")
    counts = ("whole rows %d, corrections %d, faults %d"
              % (len(table.whole), corrections, len(findings)))
    return Outcome(None, counts, findings)


def _same_file(now_path, earlier_path):
    """True when two paths that both name regular files name the same file."""
    try:
        return os.path.samefile(now_path, earlier_path)
    except (OSError, ValueError):
        return False


def check_earlier(now, earlier, same=False):
    """Compare a table file's bytes with an earlier copy's. ``now`` and ``earlier`` are the
    pairs that ``read_source`` returns; ``same`` is True when both paths name one file."""
    if now[1] is not None:
        return _dead(_FILE_STATE[now[1]])
    if earlier[1] is not None:
        return _dead(_EARLIER_STATE[earlier[1]])
    data, old = now[0], earlier[0]
    if not old:
        return _dead("earlier copy empty")
    if same:
        return _dead("earlier copy is the table file itself")
    counts = "bytes earlier %d, bytes now %d" % (len(old), len(data))
    common = min(len(data), len(old))
    if data[:common] != old[:common]:
        position = 0
        while data[position] == old[position]:
            position += 1
        line = 1 + len(_BREAK.findall(data[:position]))
        return Outcome(None, counts, [(line, "differs from the earlier copy")])
    if len(data) < len(old):
        return Outcome(None, counts, [(None, "shorter than the earlier copy")])
    return Outcome(None, counts, [])


# ------------------------------------------------------------------ the self-test

def _tsv(text):
    return parse_table(text.encode("utf-8"), "tsv")


def _planted():
    """(kind, call, expected) for each planted fault. ``call`` looks the check up when it
    runs, so a check that is replaced is the one that is tested."""
    origins = _tsv("origin\no-1\no-2\no-3\n")
    single = ("single",)
    return [
        ("table", lambda: check_table(_tsv("k\tv\nk1\ta\nk2\n"), "k"),
         (None, "whole rows 1, ragged rows 1, empty keys 0, repeats 0, keys with repeats 0",
          [(3, "fields 1, the header has 2")])),
        ("table", lambda: check_table(_tsv("k\tv\nk1\ta\n\tb\n"), "k"),
         (None, "whole rows 2, ragged rows 0, empty keys 1, repeats 0, keys with repeats 0",
          [(3, "empty key")])),
        ("table", lambda: check_table(_tsv("k\tv\nk1\ta\nk1\tb\nk1\tc\n"), "k"),
         (None, "whole rows 3, ragged rows 0, empty keys 0, repeats 2, keys with repeats 1",
          [(3, "repeated key, first on line 2"), (4, "repeated key, first on line 2")])),
        ("reference",
         lambda: check_references(_tsv("k\tc\nk1\to-1\nk2\to-9\nk3\t\n"), "c", origins,
                                  "origins", "origin", single),
         (None, "whole rows 3, blank 1, references 2, dangling 1, "
                "rows with dangling 1, distinct dangling 1", [(3, "dangling 1")])),
        ("required", lambda: check_required(_tsv("k\tg\nk1\tA\nk2\t\n"), "g"),
         (None, "whole rows 2, empty 1", [(3, "empty")])),
        ("values", lambda: check_values(_tsv("k\tg\nk1\tA\nk2\tZ\nk3\t\n"), "g", ("A", "B")),
         (None, "whole rows 3, filled 2, outside the set 1", [(3, "outside the set")])),
        ("dates", lambda: check_dates(_tsv("k\td\nk1\t2026-01-05\nk2\t2026-02-30\nk3\t\n"), "d"),
         (None, "whole rows 3, filled 2, not a date 1", [(3, "not a date")])),
        ("corrections",
         lambda: check_corrections(_tsv("k\tc\td\nk1\t\t2026-01-01\nk2\tk2\t2026-01-02\n"),
                                   "k", "c", "d"),
         (None, "whole rows 2, corrections 1, faults 1", [(3, "corrects itself")])),
        ("corrections",
         lambda: check_corrections(_tsv("k\tc\td\nk1\t\t2026-01-01\nk2\tk8\t2026-01-02\nk8\n"),
                                   "k", "c", "d"),
         (None, "whole rows 2, corrections 1, faults 1",
          [(3, "corrects a ragged row, line 4")])),
        ("corrections",
         lambda: check_corrections(_tsv("k\tc\td\nk1\t\t2026-01-01\nk2\tk9\t2026-01-02\n"),
                                   "k", "c", "d"),
         (None, "whole rows 2, corrections 1, faults 1", [(3, "corrects a missing row")])),
        ("corrections",
         lambda: check_corrections(
             _tsv("k\tc\td\nk1\t\t2026-01-01\nk1\t\t2026-01-02\nk3\tk1\t2026-01-03\n"),
             "k", "c", "d"),
         (None, "whole rows 3, corrections 1, faults 1",
          [(4, "corrects a key that is not unique")])),
        ("corrections",
         lambda: check_corrections(_tsv("k\tc\td\nk1\tk2\t2026-01-01\nk2\t\t2026-01-02\n"),
                                   "k", "c", "d"),
         (None, "whole rows 2, corrections 1, faults 1", [(2, "corrects a later row, line 3")])),
        ("corrections",
         lambda: check_corrections(_tsv("k\tc\td\nk1\t\tsoon\nk2\tk1\t2026-01-02\n"),
                                   "k", "c", "d"),
         (None, "whole rows 2, corrections 1, faults 1",
          [(3, "dates cannot be compared, line 2")])),
        ("corrections",
         lambda: check_corrections(_tsv("k\tc\td\nk1\t\t2026-01-05\nk2\tk1\t2026-01-04\n"),
                                   "k", "c", "d"),
         (None, "whole rows 2, corrections 1, faults 1",
          [(3, "dated before the row it corrects, line 2")])),
        ("earlier", lambda: check_earlier((b"a\nb\nc\n", None), (b"a\nB\n", None)),
         (None, "bytes earlier 4, bytes now 6", [(2, "differs from the earlier copy")])),
        ("earlier", lambda: check_earlier((b"a\r\nb\rc\n", None), (b"a\r\nb\rd\n", None)),
         (None, "bytes earlier 7, bytes now 7", [(3, "differs from the earlier copy")])),
        ("earlier", lambda: check_earlier((b"a\n", None), (b"a\n", None), True),
         ("earlier copy is the table file itself", "", [])),
        ("earlier", lambda: check_earlier((b"a\n", None), (b"a\nb\n", None)),
         (None, "bytes earlier 4, bytes now 2", [(None, "shorter than the earlier copy")])),
        ("rule single",
         lambda: check_references(_tsv("k\tc\nk1\to-1\nk2\t o-1\nk3\tO-1\n"), "c", origins,
                                  "origins", "origin", single),
         (None, "whole rows 3, blank 0, references 3, dangling 2, "
                "rows with dangling 2, distinct dangling 2",
          [(3, "dangling 1"), (4, "dangling 1")])),
        ("rule list",
         lambda: check_references(_tsv("k\tc\nk1\to-1, o-2\nk2\to-1;o-9,,\n"), "c", origins,
                                  "origins", "origin", ("list", ",;")),
         (None, "whole rows 2, blank 0, references 4, dangling 1, "
                "rows with dangling 1, distinct dangling 1", [(3, "dangling 1")])),
        ("rule pattern",
         lambda: check_references(
             _tsv("k\tc\nk1\tsee o-1 and o-2\nk2\to-3 then o-99\n"), "c", origins, "origins",
             "origin", ("pattern", re.compile(r"o-[0-9]+"))),
         (None, "whole rows 2, blank 0, references 4, dangling 1, "
                "rows with dangling 1, distinct dangling 1", [(3, "dangling 1")])),
    ]


def _self_test():
    """The kind of the first check that does not report exactly its planted fault, or None."""
    for kind, call, expected in _planted():
        if call().key() != (expected[0], expected[1], expected[2]):
            return kind
    return None


# ------------------------------------------------------------------ the declaration

class _State(reader_harness.ParseState):
    """A parse state whose problems say ``declaration line``."""

    def __init__(self):
        reader_harness.ParseState.__init__(self)
        self.numbered = []

    def bad(self, number, message):
        line = "declaration line %d: %s" % (number, message)
        self.problems.append(line)
        self.numbered.append((number, line))

    def pattern(self, number, text, flags=0):
        # A repetition count that is too large raises OverflowError, and a deeply nested
        # group RecursionError, rather than re.error.
        try:
            return reader_harness.ParseState.pattern(self, number, text, flags)
        except (OverflowError, RecursionError):
            self.bad(number, "not a valid pattern: %s" % reader_harness.show(text))
            return False


class Declaration(object):
    def __init__(self):
        self.tables = []
        self.references = []
        self.required = []
        self.values = []
        self.dates = []
        self.corrections = []
        self.earlier = []


def _table_item(state, number, parts, decl, names):
    if len(parts) != 4:
        state.bad(number, "a table is written: name | file | format | key column")
        return
    name, file, fmt, key = parts
    if not reader_harness.NAME.match(name):
        state.bad(number, "a table name holds letters, digits and - only: %s"
                  % reader_harness.short(name))
        return
    if name in names:
        state.bad(number, "the table %s is named twice" % name)
        return
    names.add(name)
    if fmt not in ("tsv", "csv"):
        state.bad(number, "a format is tsv or csv: %s" % reader_harness.short(fmt))
        return
    decl.tables.append((name, file, fmt, key))


def _rule(state, number, text):
    """The cell rule a ``rule`` field writes, or None (a problem is recorded)."""
    if text == "single":
        return ("single",)
    if text.startswith("list "):
        characters = text[len("list "):]
        if " " in characters:
            state.bad(number, "a space cannot be a list separator")
            return None
        return ("list", characters)
    if text.startswith("pattern "):
        regex = text[len("pattern "):]
        if not state.pattern(number, regex):
            return None
        return ("pattern", re.compile(regex))
    state.bad(number, "a rule is single, list CHARACTERS or pattern REGEX: %s"
              % reader_harness.short(text))
    return None


def _repeat(state, seen, key, number, parts):
    """True when an item repeats an earlier item under the same key, field for field; the
    problem is recorded."""
    first = seen.setdefault((key, tuple(parts)), number)
    if first != number:
        state.bad(number, "the same item as line %d" % first)
        return True
    return False


def _known(state, number, names, *tables):
    """True when every table named exists; each one that does not is a problem."""
    for table in tables:
        if table not in names:
            state.bad(number, "no table named %s" % reader_harness.short(table))
            return False
    return True


def parse_declaration(text):
    """(Declaration, problem lines). A declaration with problems cannot be run."""
    state = _State()
    _scalars, lists = reader_harness.structure(state, text, LIST_KEYS, ())
    decl = Declaration()
    names = set()
    seen = {}
    for number, item in lists.get("tables", []):
        parts = state.fields(number, item)
        if parts is not None and not _repeat(state, seen, "tables", number, parts):
            _table_item(state, number, parts, decl, names)
    shapes = (
        ("references", 5, "a reference is written: table | column | table | column | rule"),
        ("required", 2, "required is written: table | column"),
        ("values", 3, "values is written: table | column | value | ..."),
        ("dates", 2, "dates is written: table | column"),
        ("corrections", 3, "corrections is written: table | column | date column"),
        ("earlier", 2, "earlier is written: table | file"),
    )
    for key, width, message in shapes:
        for number, item in lists.get(key, []):
            parts = state.fields(number, item)
            if parts is None or _repeat(state, seen, key, number, parts):
                continue
            if len(parts) < width or (len(parts) > width and key != "values"):
                state.bad(number, message)
                continue
            if key == "references":
                if not _known(state, number, names, parts[0], parts[2]):
                    continue
                rule = _rule(state, number, parts[4])
                if rule is not None:
                    decl.references.append((parts[0], parts[1], parts[2], parts[3], rule))
                continue
            if not _known(state, number, names, parts[0]):
                continue
            if key == "required":
                decl.required.append((parts[0], parts[1]))
            elif key == "values":
                decl.values.append((parts[0], parts[1], tuple(parts[2:])))
            elif key == "dates":
                decl.dates.append((parts[0], parts[1]))
            elif key == "corrections":
                decl.corrections.append((parts[0], parts[1], parts[2]))
            else:
                decl.earlier.append((parts[0], parts[1]))
    problems = [line for _number, line in sorted(state.numbered, key=lambda p: p[0])]
    if not lists.get("tables"):
        problems.append("the declaration names no table")
    return decl, problems


def _declaration_text(path):
    """(text, None) or (None, the one-line reason the declaration cannot be used)."""
    name = _shown(os.path.basename(path.rstrip("/")) or path)
    data, code = read_source(path)
    if code is not None:
        return None, "cannot read the declaration: %s" % name
    if data.startswith(BOM):
        data = data[len(BOM):]
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "the declaration is not valid UTF-8: %s" % name


# ------------------------------------------------------------------ the run

def _cannot(*reasons):
    return reader_harness.Result(2, False, error="\n".join("cannot run: %s" % r for r in reasons))


def run(declaration_path, report_only=False):
    failed = _self_test()
    if failed is not None:
        return _cannot("self-test failed: %s" % failed)
    text, reason = _declaration_text(declaration_path)
    if reason is not None:
        return _cannot(reason)
    decl, problems = parse_declaration(text)
    if problems:
        return _cannot(*problems)
    folder = os.path.dirname(declaration_path)
    files = {}
    tables = {}
    for name, file, fmt, _key in decl.tables:
        files[name] = file
        tables[name] = load_table(os.path.join(folder, file), fmt)
    keys = dict((name, key) for name, _file, _fmt, key in decl.tables)
    checks = []
    for name, _file, _fmt, key in decl.tables:
        checks.append(("table %s" % name, name, check_table(tables[name], key)))
    for name, column, target, target_column, rule in decl.references:
        label = "references %s.%s to %s.%s" % (name, _shown(column), target,
                                               _shown(target_column))
        checks.append((label, name, check_references(tables[name], column, tables[target],
                                                     target, target_column, rule)))
    for name, column in decl.required:
        checks.append(("required %s.%s" % (name, _shown(column)), name,
                       check_required(tables[name], column)))
    for name, column, allowed in decl.values:
        checks.append(("values %s.%s" % (name, _shown(column)), name,
                       check_values(tables[name], column, allowed)))
    for name, column in decl.dates:
        checks.append(("dates %s.%s" % (name, _shown(column)), name,
                       check_dates(tables[name], column)))
    for name, column, date_column in decl.corrections:
        checks.append(("corrections %s.%s" % (name, _shown(column)), name,
                       check_corrections(tables[name], keys[name], column, date_column)))
    for name, earlier_file in decl.earlier:
        now_path = os.path.join(folder, files[name])
        old_path = os.path.join(folder, earlier_file)
        now = read_source(now_path)
        old = read_source(old_path)
        same = now[1] is None and old[1] is None and _same_file(now_path, old_path)
        checks.append(("earlier %s" % name, name, check_earlier(now, old, same)))
    lines = []
    tally = {"OK": 0, "FAIL": 0, "DEAD": 0}
    for label, name, outcome in checks:
        if outcome.dead is not None:
            tally["DEAD"] += 1
            lines.append("%-6s%s: %s" % ("DEAD", label, outcome.dead))
            continue
        status = "FAIL" if outcome.findings else "OK"
        tally[status] += 1
        lines.append("%-6s%s: %s" % (status, label, outcome.counts))
        shown = _shown(files[name])
        for number, finding in outcome.findings:
            if number is None:
                lines.append("%s: %s" % (shown, finding))
            else:
                lines.append("%s:%d: %s" % (shown, number, finding))
    lines.append("checks: OK %d, FAIL %d, DEAD %d" % (tally["OK"], tally["FAIL"], tally["DEAD"]))
    if tally["DEAD"]:
        code = 2
    elif tally["FAIL"] and not report_only:
        code = 1
    else:
        code = 0
    return reader_harness.Result(code, True, text="\n".join(lines) + "\n")
