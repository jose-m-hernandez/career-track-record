"""The series file of ``ab``: which draft was read against which parent, and what each round
said.

The behaviour is stated in docs/specs/series.md (revision 1 of the series spec). One TSV per
series of drafts, made by hand; ``ab`` appends one row when it scores the round that admits a
draft, and adds one item to that row's ``result`` cell when a follow-up round of the draft is
scored. A plan with no ``series`` key never reaches this module's file code, and ``fcntl`` is
imported only here, inside a function, only for a plan that names ``series``.

Every rule that can stop a command before it reads or writes anything is in ``plan_problems``
(checks 1 to 6 of the spec's section 6). The one write is ``after_result``: it takes a lock on
``<series file>.lock``, rereads the file, runs the checks again, builds the new bytes,
validates them and replaces the file in one step.

The paths the write touches are checked against the configured record folder like any other
write (``refusal`` before the result exists, once more under the lock): the series file, its
lock file and a temporary file in the folder of the series file.
"""

import datetime
import errno
import os
import re
import stat
import time
import unicodedata

from career_track_record import reader_harness as harness
from career_track_record import write_guard
from career_track_record.barred import printed_path

HEADER = "draft\tparent\tfile_sha256\tposting_sha256\tround\tplan_sha256\tresult\tdate\tnote"
COLUMNS = tuple(HEADER.split("\t"))
NO_FCNTL = "series needs a POSIX file lock (fcntl), which this platform does not have"
BAD_FOLDER = ("the folder name holds a character a series row cannot carry (; @ or a control "
              "character)")
KINDS = ("extends", "amends", "replicate")

# The lock's wait, in seconds: one deadline for opening and locking, counted from the start of
# the open, and the pause between two attempts. Module-level so that a test can shorten them.
LOCK_DEADLINE = 10.0
LOCK_RETRY = 0.1

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NAME = harness.NAME
_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})\Z")
_ITEM = re.compile(r"([^@]*)@([0-9a-f]{64})(?: (extends|amends|replicate))?: (.*)\Z", re.S)
_VERDICT = re.compile(r"h[0-9]+ (?:SUPPORTED|REFUTED|INCONCLUSIVE|TIE)\Z")
_BOM = b"\xef\xbb\xbf"


class Fault(Exception):
    """The series file breaks a rule of section 3; the message is the one line to print."""


class WriteFailed(Exception):
    """The write after the result failed; the message is the reason printed after
    ``series: not written: ``."""


def _reason(exc):
    """One printable line for an error: the system's own words for an OSError, else the
    message, else the class name."""
    return harness.show(getattr(exc, "strerror", None) or str(exc) or exc.__class__.__name__)


# ------------------------------------------------------------------ the seams
# Each of these is one call the write makes, named here so that a test can make it fail, or
# change what the file holds at that moment. None of them is reachable from a plan, an
# option or the environment.

def _fcntl():
    """The fcntl module, or None on a platform without it. The one capability check every
    command uses, and the only place fcntl is imported (spec 5a)."""
    try:
        import fcntl
    except ImportError:
        return None
    return fcntl


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def _reread(path):
    """The series file read again under the lock."""
    return _read_bytes(path)


def _lstat(path):
    return os.lstat(path)


def _open(path, flags, mode):
    return os.open(path, flags, mode)


def _flock(fd):
    fcntl = _fcntl()
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _build(old_text, rows, facts, item):
    """The new bytes of the file: the old ones plus the new row, or the old ones with the one
    item added at the end of the one ``result`` cell."""
    if facts.kind is None:
        return old_text + _row_line(facts, item)
    row = [r for r in rows if r["draft"] == facts.draft][0]
    lines = old_text.split("\n")
    fields = lines[row["line"] - 1].split("\t")
    fields[COLUMNS.index("result")] += "; " + item
    lines[row["line"] - 1] = "\t".join(fields)
    return "\n".join(lines)


def _write_temp(path, data, mode):
    """Create ``path`` (it must not exist) holding ``data``, with the mode of the file it
    will replace."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def _replace(source, target):
    """The commit point."""
    os.replace(source, target)


def _close(fd):
    os.close(fd)


# ------------------------------------------------------------------ the file (section 3)

def round_fault(text):
    """What is wrong with a ``round``, or None: a relative path written with ``/``, no empty
    segment, no ``.`` or ``..`` segment, no ``;``, no ``@``, no control character."""
    if not text:
        return "is empty"
    for ch in text:
        if ch in ";@" or unicodedata.category(ch) == "Cc":
            return "holds ; @ or a control character"
    segments = text.split("/")
    if "" in segments:
        return "has an empty segment, or a leading or trailing /"
    if "." in segments or ".." in segments:
        return "has a . or .. segment"
    return None


def parse_result(cell, round_, plan):
    """The items of a ``result`` cell as (round, digest, kind) in order, or Fault text raised
    as ValueError. An item is read from its left: the round up to the first ``@``, the 64
    digits, an optional kind, ``: ``; only then are the verdicts split on ``, ``."""
    items = []
    for index, text in enumerate(cell.split("; ")):
        match = _ITEM.match(text)
        if not match:
            raise ValueError("item %d is not <round>@<64 hex>[ kind]: verdicts" % (index + 1))
        item_round, digest, kind, verdicts = match.groups()
        fault = round_fault(item_round)
        if fault:
            raise ValueError("item %d: the round %s" % (index + 1, fault))
        for piece in verdicts.split(", "):
            if not _VERDICT.match(piece):
                raise ValueError("item %d: not a verdict: %s" % (index + 1, harness.short(piece)))
        if index == 0:
            if kind is not None:
                raise ValueError("the first item has a kind")
            if item_round != round_ or digest != plan:
                raise ValueError("the first item is not this row's round and plan_sha256")
        elif kind is None:
            raise ValueError("item %d has no kind" % (index + 1))
        items.append((item_round, digest, kind))
    return items


def _check_row(row, rows_by_draft):
    """Every column rule of section 3 on one row: the (column, fault) of the first that breaks,
    else None. ``rows_by_draft`` holds the draft of each earlier row and its line."""
    draft = row["draft"]
    if not _NAME.match(draft):
        return "draft", "letters, digits and - only, and not empty: %s" % harness.short(draft)
    if draft in rows_by_draft:
        return "draft", "repeated, first on line %d" % rows_by_draft[draft]
    parent = row["parent"]
    if parent and parent not in rows_by_draft:
        return "parent", "is no earlier row: %s" % harness.short(parent)
    if not _HEX.match(row["file_sha256"]):
        return "file_sha256", "is not 64 lowercase hex digits"
    filled = bool(row["round"])
    for column in ("posting_sha256", "plan_sha256"):
        if row[column] and not _HEX.match(row[column]):
            return column, "is not empty or 64 lowercase hex digits"
    if bool(row["posting_sha256"]) != filled:
        return "posting_sha256", "empty while round is filled" if filled \
            else "filled while round is empty"
    if filled:
        fault = round_fault(row["round"])
        if fault:
            return "round", fault
    if bool(row["plan_sha256"]) != filled:
        return "plan_sha256", "empty while round is filled" if filled \
            else "filled while round is empty"
    if bool(row["result"]) != filled:
        return "result", "empty while round is filled" if filled else "filled while round is empty"
    if filled:
        try:
            row["items"] = parse_result(row["result"], row["round"], row["plan_sha256"])
        except ValueError as exc:
            return "result", str(exc)
    else:
        row["items"] = []
    match = _DATE.match(row["date"])
    try:
        datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except (AttributeError, ValueError):
        return "date", "is not a real YYYY-MM-DD date: %s" % harness.short(row["date"])
    return None


def parse(data, shown):
    """The rows of the series file's bytes, each a dict of its nine columns plus ``line`` and
    ``items``, or a Fault naming ``<file>:<line>: <column>: <fault>``. ``shown`` is the file as
    the plan writes it, already escaped."""
    if data.startswith(_BOM):
        raise Fault("%s:1: the file starts with a byte-order mark" % shown)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Fault("%s:%d: the file is not valid UTF-8" % (shown, data.count(b"\n", 0,
                                                                              exc.start) + 1))
    at = text.find("\r")
    if at >= 0:
        raise Fault("%s:%d: a carriage return; line breaks are LF only"
                    % (shown, text.count("\n", 0, at) + 1))
    if not text.endswith("\n"):
        raise Fault("%s:%d: the file does not end with a line break"
                    % (shown, text.count("\n") + 1))
    lines = text.split("\n")[:-1]
    if lines[0] != HEADER:
        raise Fault("%s:1: the header is not exactly: %s" % (shown, HEADER.replace("\t", " ")))
    rows, by_draft = [], {}
    for number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != len(COLUMNS):
            raise Fault("%s:%d: fields %d, the header has %d"
                        % (shown, number, len(fields), len(COLUMNS)))
        row = dict(zip(COLUMNS, fields))
        row["line"] = number
        broken = _check_row(row, by_draft)
        if broken:
            raise Fault("%s:%d: %s: %s" % (shown, number, broken[0], broken[1]))
        by_draft[row["draft"]] = number
        rows.append(row)
    return rows


def load(path, shown, under_lock=False):
    """(text, rows) of the series file after check 1: it exists, is a regular file and not a
    symbolic link, can be read, lies in a folder that can be written, and every rule of
    section 3 holds. Raises Fault."""
    try:
        status = os.lstat(path)
    except (FileNotFoundError, ValueError):
        # a name with a NUL byte cannot be a file: the same refusal as a file that is not there
        raise Fault("%s: no such file; a person makes the series file by hand, with its header "
                    "and the parent's row, and the tool never creates it" % shown)
    except OSError as exc:
        raise Fault("%s: cannot read: %s" % (shown, harness.show(harness.reason_of(exc))))
    if stat.S_ISLNK(status.st_mode):
        raise Fault("%s: is a symbolic link; the write replaces the file and would swap the "
                    "link" % shown)
    if not stat.S_ISREG(status.st_mode):
        raise Fault("%s: is not a regular file" % shown)
    if not os.access(os.path.dirname(path), os.W_OK | os.X_OK):
        raise Fault("%s: its folder cannot be written" % shown)
    try:
        data = (_reread if under_lock else _read_bytes)(path)
    except OSError as exc:
        raise Fault("%s: cannot read: %s" % (shown, harness.show(harness.reason_of(exc))))
    return data.decode("utf-8", errors="replace"), parse(data, shown)


# ------------------------------------------------------------------ what a plan says

class Facts(object):
    """What the checks and the write need from one plan: who the draft and its parent are,
    which round this is, and the hashes of what the comparison read."""


def utc_day(now):
    """The UTC day, ``YYYY-MM-DD``, of ``now``: a datetime (a naive one is read as UTC), or the
    real clock when None. Never local time."""
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    elif now.tzinfo is not None:
        now = now.astimezone(datetime.timezone.utc)
    return now.strftime("%Y-%m-%d")


def _version_digest(folder, label, recorded):
    """(sha256, what was hashed) of what the comparison read of a version file, or
    (None, None) when the file is not there (the freeze reports that). A name ending in
    ``.pdf``, in any case, is hashed as its extracted text, as ``ab`` reads it; any other file
    is hashed as the freeze did. Raises harness.Unreadable for a PDF whose text cannot be got."""
    path = os.path.join(folder, label)
    if not os.path.isfile(path):
        return None, None
    if label.lower().endswith(".pdf"):
        return harness.sha256_text(harness.read_text(path)), "the pdftotext text of the file"
    if recorded and recorded.get(label):
        return recorded[label], "the file's bytes"
    return harness.sha256_file(path), "the file's bytes"


def _earlier_digest(folder, named):
    """The sha256 the named freeze file records for the plan beside it, or None."""
    freeze_path = os.path.join(folder, named)
    try:
        entries = dict(harness.read_freeze(freeze_path))
    except (OSError, UnicodeDecodeError):
        return None
    return entries.get(os.path.basename(freeze_path)[:-len(harness.FREEZE_SUFFIX)])


def _series_abs(plan, plan_path):
    """The series file's path as the write uses it: the plan's own text joined to the plan's
    folder, with ``.`` and ``..`` collapsed as written (no link followed)."""
    return os.path.abspath(os.path.join(harness.folder_of(plan_path), plan.series))


def facts_of(plan, plan_path, now, recorded):
    folder = harness.folder_of(plan_path)
    f = Facts()
    f.plan = plan
    f.series_text = plan.series
    f.shown = harness.show(plan.series)
    f.series_abs = _series_abs(plan, plan_path)
    f.environ = None
    f.relative = os.path.relpath(folder, os.path.dirname(f.series_abs))
    f.round = f.relative.replace(os.sep, "/")
    f.parent, f.draft = plan.comparisons[0]
    f.today = utc_day(now)
    f.note = plan.series_note or ""
    f.kind, f.key, named = None, None, None
    for kind, key, value in (("extends", "extends", plan.extends),
                             ("amends", "amends", plan.amends),
                             ("replicate", "replicate-of", plan.replicate_of)):
        if value is not None:
            f.kind, f.key, named = kind, key, value
    f.earlier = None if named is None else _earlier_digest(folder, named)
    f.plan_digest = (recorded.get(os.path.basename(plan_path)) if recorded
                     else harness.sha256_file(plan_path))
    f.posting_digest = recorded.get(plan.posting) if recorded else None
    f.unreadable = []
    f.digests = {}
    for name in (f.parent, f.draft):
        label = plan.version_path(name)
        try:
            f.digests[name] = _version_digest(folder, label, recorded)
        except harness.Unreadable as exc:
            f.digests[name] = (None, None)
            f.unreadable.append("cannot read %s: %s" % (harness.show(label), exc))
    return f


def _row_line(f, item):
    """The line of a new row: the nine cells joined by tabs, ended by one LF."""
    return "\t".join([f.draft, f.parent, f.digests[f.draft][0], f.posting_digest, f.round,
                      f.plan_digest, item, f.today, f.note]) + "\n"


def item_of(f, verdicts):
    """The item for this round: ``<round>@<plan64>[ <kind>]: <verdicts>``."""
    return "%s@%s%s: %s" % (f.round, f.plan_digest, " " + f.kind if f.kind else "",
                            ", ".join("%s %s" % pair for pair in verdicts))


# ------------------------------------------------------------------ the checks (section 6)

def _folder_problems(f):
    """Check 3: the plan's folder lies strictly below the series file's, and no segment of the
    path between them holds a character a row cannot carry. The path is refused, never
    encoded."""
    segments = f.relative.split(os.sep)
    if f.relative == "." or ".." in segments:
        return ["%s: the plan's folder is not strictly below the folder of the series file"
                % f.shown]
    if any(ch in ";@" or unicodedata.category(ch) == "Cc" for ch in f.round):
        return ["%s: %s" % (harness.show(f.round), BAD_FOLDER)]
    return []


def recorded_plan(rows, digest):
    """The first row whose ``plan_sha256``, or whose items, hold this plan's full digest."""
    for row in rows:
        if row["plan_sha256"] == digest or any(d == digest for _r, d, _k in row["items"]):
            return row
    return None


def _mismatch(name, computed, how, row):
    return ("%s: the plan's file is not the file the series records (computed %s from %s; the "
            "row holds %s)" % (name, computed, how, row["file_sha256"]))


def _row_checks(f, rows):
    """Checks 2, 4 and 5 on the parsed rows: the problems, in order."""
    by_draft = dict((r["draft"], r) for r in rows)
    problems = []
    parent = by_draft.get(f.parent)
    digest, how = f.digests[f.parent]
    if parent is None:
        problems.append("%s: not a row of the series file %s" % (f.parent, f.shown))
    elif digest is not None and parent["file_sha256"] != digest:
        problems.append(_mismatch(f.parent, digest, how, parent))
    row = by_draft.get(f.draft)
    if f.kind is None:
        if row is not None and row["plan_sha256"] != f.plan_digest:
            problems.append("%s: the series already holds this draft (line %d); a second round "
                            "of a draft is a follow-up plan, with extends, amends or "
                            "replicate-of" % (f.draft, row["line"]))
        elif (row is None and parent is not None
              and recorded_plan(rows, f.plan_digest) is None and f.today < parent["date"]):
            problems.append("%s: its row is dated %s, after today, %s; a new row dated before "
                            "the row it corrects is one record faults"
                            % (f.parent, parent["date"], f.today))
        return problems
    if row is None:
        problems.append("%s: not a row of the series file %s; a follow-up adds to the row of a "
                        "draft the series already holds" % (f.draft, f.shown))
        return problems
    digest, how = f.digests[f.draft]
    if digest is not None and row["file_sha256"] != digest:
        problems.append(_mismatch(f.draft, digest, how, row))
    if row["parent"] != f.parent:
        problems.append("%s: its row (line %d) has parent %s, not %s"
                        % (f.draft, row["line"], row["parent"] or "none", f.parent))
    if f.earlier is not None and row["plan_sha256"] != f.earlier \
            and not any(d == f.earlier for _r, d, _k in row["items"]):
        problems.append("%s: plan %s is not one row %s (line %d) records"
                        % (f.key, f.earlier[:12], f.draft, row["line"]))
    return problems


def _checks(f, under_lock=False):
    """(problems, text, rows) of checks 1 to 5 against the series file as it is now."""
    problems = _folder_problems(f) + list(f.unreadable)
    try:
        text, rows = load(f.series_abs, f.shown, under_lock)
    except Fault as exc:
        return problems + [str(exc)], None, None
    return problems + _row_checks(f, rows), text, rows


def _series_targets(series_abs):
    """The three complete paths the series write touches: the series file, its lock file and
    the temporary file of the replacement. The temporary file's name is made at the write; the
    pid is real and the rest fixed, because the check is on the folder, and the name only
    matters for the path message 12 prints."""
    return [series_abs, series_abs + ".lock", "%s.%d.%s.tmp" % (series_abs, os.getpid(), "check")]


def refusal(plan, plan_path, sub, environ=None):
    """None, or (exit code, one line) when ``freeze``, ``run`` or ``score`` (``sub``) of a
    plan with ``series`` must stop before it reads or writes anything because the record
    folder does not allow the write (setup spec 7.5). The plan's own targets are asked first,
    and a refusal there is printed as it is, with no mention of the series file. Only when they
    pass are the three series paths asked, and then the line ends with the series file as the
    plan names it. Nothing is read, written or created."""
    if plan.series is None:
        return None
    try:
        write_guard.recheck(write_guard.plan_targets(sub, plan_path), environ)
    except write_guard.Refusal as refused:
        return refused.code, refused.line
    try:
        write_guard.recheck(_series_targets(_series_abs(plan, plan_path)), environ)
    except write_guard.Refusal as refused:
        return refused.code, "%s (series file %s)" % (refused.line, printed_path(plan.series))
    return None


def plan_problems(plan, plan_path, now=None, recorded=None):
    """The problems that stop ``freeze``, ``run`` (before any read) and ``score`` (before it
    writes a result) for a plan with ``series``, in order; none for a plan without it.
    ``recorded`` is the freeze's hashes by label, or None at freeze."""
    if plan.series is None:
        return []
    if _fcntl() is None:
        return ["plan line %d: %s" % (plan.series_line, NO_FCNTL)]
    return _checks(facts_of(plan, plan_path, now, recorded))[0]


# ------------------------------------------------------------------ the write (section 5)

def _take_lock(f, started):
    """Open and lock ``<series file>.lock``: the descriptor, holding LOCK_EX. One deadline
    counted from ``started`` covers the open and the lock, and nothing here blocks past it."""
    lock = f.series_abs + ".lock"
    shown = harness.show(f.series_text + ".lock")
    deadline = started + LOCK_DEADLINE

    def cannot(reason):
        return WriteFailed("cannot take %s: %s" % (shown, harness.show(reason)))

    try:
        existed = True
        status = _lstat(lock)
    except FileNotFoundError:
        existed = False
    except OSError as exc:
        raise cannot(harness.reason_of(exc))
    if existed and not stat.S_ISREG(status.st_mode):
        raise cannot("not a regular file")
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = None
    while fd is None:
        try:
            fd = _open(lock, flags, 0o600)
        except OSError as exc:
            if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise cannot(harness.reason_of(exc))
            if time.monotonic() >= deadline:
                raise cannot("timed out")
            time.sleep(LOCK_RETRY)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise cannot("not a regular file")
        if not existed:
            # Only a lock file this call made: a restrictive umask must not leave it
            # unwritable by its owner. An existing lock file keeps its mode.
            os.fchmod(fd, 0o600)
        while True:
            try:
                _flock(fd)
                return fd
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise cannot("timed out waiting for the lock")
                time.sleep(LOCK_RETRY)
            except OSError as exc:
                raise cannot(harness.reason_of(exc))
    except BaseException:
        os.close(fd)
        raise


def _validate(old_text, new_text, rows, f, item):
    """Check 1 on the new bytes, and that they differ from the old ones only by the added line
    or the added item."""
    parse(new_text.encode("utf-8"), f.shown)
    if f.kind is None:
        if new_text != old_text + _row_line(f, item):
            raise WriteFailed("the new bytes are not the old bytes and one new row")
        return
    row = [r for r in rows if r["draft"] == f.draft][0]
    old_lines, new_lines = old_text.split("\n"), new_text.split("\n")
    at = row["line"] - 1
    if len(old_lines) != len(new_lines) or old_lines[:at] != new_lines[:at] \
            or old_lines[at + 1:] != new_lines[at + 1:]:
        raise WriteFailed("the new bytes differ from the old bytes outside one row")
    old_fields, new_fields = old_lines[at].split("\t"), new_lines[at].split("\t")
    cell = COLUMNS.index("result")
    if len(new_fields) != len(old_fields) or any(
            a != b for i, (a, b) in enumerate(zip(old_fields, new_fields)) if i != cell):
        raise WriteFailed("the new bytes differ from the old bytes outside one cell")
    if new_fields[cell] != old_fields[cell] + "; " + item:
        raise WriteFailed("the new cell is not the old cell and one item")


LATE_TAIL = "; the result is kept; fix this, then re-run ab score on the plan to add the row"


def _recheck_late(f):
    """The record-folder check again, under the lock, once the result exists. A refusal of any
    kind is a failure of this write and nothing more: the line drops the message's leading
    ``refused: `` or ``cannot run: `` (a command that ran and left a result does not say it
    cannot run), says the result is kept, and the exit status stays at most 1."""
    try:
        write_guard.recheck(_series_targets(f.series_abs), f.environ)
    except write_guard.Refusal as refused:
        line = refused.line
        for lead in ("refused: ", "cannot run: "):
            if line.startswith(lead):
                line = line[len(lead):]
                break
        raise WriteFailed(line + LATE_TAIL)


def _locked_write(f, verdicts, outcome):
    """Steps 1 to 4 of section 5 and the release. Returns the line to print; raises
    WriteFailed from any failure before the replacement returned."""
    started = time.monotonic()
    fd = None
    temp = None
    committed = False
    try:
        fd = _take_lock(f, started)
        problems, old_text, rows = _checks(f, under_lock=True)
        if problems:
            raise WriteFailed("; ".join(problems))
        _recheck_late(f)
        if f.posting_digest is None or f.plan_digest is None:
            raise WriteFailed("the freeze holds no hash for the posting or the plan")
        if f.digests[f.draft][0] is None:
            raise WriteFailed("cannot hash the draft's file")
        hit = recorded_plan(rows, f.plan_digest)
        if hit is not None:
            return "series: no change: plan %s is already recorded in row %s (line %d)" % (
                f.plan_digest[:12], hit["draft"], hit["line"])
        item = item_of(f, verdicts)
        new_text = _build(old_text, rows, f, item)
        _validate(old_text, new_text, rows, f, item)
        if f.kind is None:
            line = "series: added row %s to %s" % (f.draft, f.shown)
        else:
            line = "series: added result of %s to row %s in %s" % (
                harness.show(f.round), f.draft, f.shown)
        mode = stat.S_IMODE(os.stat(f.series_abs).st_mode)
        temp = "%s.%d.%s.tmp" % (f.series_abs, os.getpid(), os.urandom(4).hex())
        _write_temp(temp, new_text.encode("utf-8"), mode)
        _replace(temp, f.series_abs)
        committed = True
        return line
    except WriteFailed:
        raise
    except Exception as exc:
        if committed:
            raise
        raise WriteFailed(_reason(exc))
    finally:
        if temp is not None:
            try:
                os.remove(temp)
            except OSError:
                pass
        if fd is not None:
            try:
                _close(fd)
            except Exception as exc:
                # An error after the replacement returned is never "not written": the row or
                # item is in the file. Before it, the failure already propagating is the one
                # that counts.
                if committed:
                    outcome["warning"] = ("series: lock release failed after the write: %s\n"
                                          % _reason(exc))


def after_result(plan, plan_path, recorded, verdicts, now=None, environ=None):
    """The series write for a plan with ``series``, after its result file exists. Returns
    (line to print, warning for standard error or "", failed). ``verdicts`` is the
    (hypothesis, verdict word) pairs of the result in plan order. ``environ`` is what the
    record-folder check reads the config from (None: this process's)."""
    outcome = {"warning": ""}
    try:
        f = facts_of(plan, plan_path, now, recorded)
        f.environ = environ
        line = _locked_write(f, verdicts, outcome)
    except WriteFailed as exc:
        return "series: not written: %s" % exc, outcome["warning"], True
    except Exception as exc:
        return "series: not written: %s" % _reason(exc), outcome["warning"], True
    return line, outcome["warning"], False
