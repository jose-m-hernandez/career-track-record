"""The harness that the reader commands share: ``track-record ab`` and ``track-record panel``.

Both commands freeze a plain-text plan and its inputs by hash, write a run folder of reads,
run the built-in fake reader inside the tool or a live reader (a command the user names)
through ``ab_reader_command``, and score the replies into a numbered result file. This module
holds the parts that are the same for both: the plan-file syntax, the freeze file and its
checks, the run folder and its errors, the live-reader preview and read, the read loop with
its spend ceiling and run log, the reply-field splitter, and the tail of every result.

What a plan means, how the fake reader answers, and how replies are scored stay in each
command's own module. Nothing here starts a program: that is ``ab_reader_command`` alone.
"""

import difflib
import hashlib
import os
import re
import shlex

from career_track_record import ab_reader_command, barred, pdf_text

# File names inside a read folder, and in the run folder. Every use goes through these.
READ_POSTING = "POSTING.txt"
READ_PROMPT = "PROMPT.txt"
READ_REPLY = "REPLY.txt"
READ_STDERR = "STDERR.txt"
READS_DIR = "reads"
KEY_FILE = "key.txt"
RUN_LOG = "run-log.txt"
RESULT_STEM = "result-"
FREEZE_SUFFIX = ".freeze"
PROMPT_LABEL = "PROMPT.txt (built into the tool)"
FAKE = "fake"
DEFAULT_READ_TIMEOUT = 600

# Everything printed that came from an argument, a file name or a file's contents goes through
# this one function (the one ``tone`` and ``barred`` print paths with), so that no value can
# split a line or hide in an invisible character.
show = barred.printed_path

NAME = re.compile(r"[A-Za-z0-9-]+\Z")
INTEGER = re.compile(r"[0-9]+\Z")
SIGNED = re.compile(r"-?[0-9]+\Z")
READ_K = re.compile(r"read ([0-9]+)\Z")
QUOTED = r'"(.+)"'
LINE_BREAK = re.compile(r"\r\n|\r|\n")
_SPACES = re.compile(r"[ \t]+")
_WHOLE = re.compile(r"-?[0-9]+\Z")


class Result(object):
    """What a call produced. ``text`` is what the command prints; ``error`` holds the
    problem lines joined with a line feed, without a final one."""

    def __init__(self, exit_code, ran, text="", error="", stopped=None):
        self.exit_code = exit_code
        self.ran = ran
        self.text = text
        self.error = error
        # The escaped reason when the run stopped early (the command writes it to standard
        # error as one ``cannot run: stopped: <reason>`` line), else None.
        self.stopped = stopped

    def __repr__(self):
        return "Result(exit_code=%r, ran=%r, error=%r)" % (
            self.exit_code, self.ran, self.error)


class Reader(object):
    """A reader. ``command`` is the word ``fake`` or the text of a live command."""

    def __init__(self, name, command=FAKE, not_blind=False, cost=1):
        self.name = name
        self.command = command
        self.not_blind = not_blind
        self.cost = cost

    @property
    def kind(self):
        return "fake" if self.command == FAKE else "live"


# ------------------------------------------------------------------ the plan file

class PlanError(Exception):
    """The plan file cannot be used. ``problems`` is a list of one-line messages."""

    def __init__(self, problems):
        Exception.__init__(self, "; ".join(problems))
        self.problems = list(problems)


class ParseState(object):
    """State of one parse: the problems found so far, each with its plan line number."""

    def __init__(self):
        self.problems = []

    def bad(self, number, message):
        self.problems.append("plan line %d: %s" % (number, message))

    def fields(self, number, text):
        """The trimmed fields of an item line, or None (a problem is recorded) if one is empty."""
        parts = [part.strip() for part in text.split(" | ")]
        if any(not part for part in parts):
            self.bad(number, "an empty field")
            return None
        return parts

    def integer(self, number, key, text, minimum=0):
        if not INTEGER.match(text) or int(text) < minimum:
            what = "a positive whole number" if minimum else "a whole number, 0 or more"
            self.bad(number, "%s must be %s" % (key, what))
            return None
        return int(text)

    def signed(self, number, key, text):
        if not SIGNED.match(text):
            self.bad(number, "%s must be a whole number" % key)
            return None
        return int(text)

    def pattern(self, number, text, flags=0):
        try:
            re.compile(text, flags)
        except re.error:
            self.bad(number, "not a valid pattern: %s" % show(text))
            return False
        return True


def short(text):
    """Text from the plan as it is shown in a message: cut to 40 characters, then escaped."""
    return show(text if len(text) <= 40 else text[:40] + "...")


def plan_text(path):
    """The text of a plan file. Raises PlanError when it cannot be read or is not UTF-8."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (OSError, ValueError):
        raise PlanError(["cannot read the plan: %s" % show(os.path.basename(path))])
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise PlanError(["the plan is not valid UTF-8: %s" % show(os.path.basename(path))])


def structure(state, text, list_keys, scalar_keys):
    """(scalars, lists): scalars maps a key to (line, value), lists a key to [(line, item)].

    Each line is ``key: value``; a list value is one item per indented line under its key.
    Blank lines and lines starting with ``#`` are ignored; an unknown or repeated key is a
    problem."""
    scalars, lists = {}, {}
    seen = set()
    current = None
    for number, raw in enumerate(LINE_BREAK.split(text), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw[0] in " \t":
            if current is None:
                state.bad(number, "an indented line that belongs to no key")
            elif current in scalar_keys:
                state.bad(number, "%s takes one value on its own line, not a list" % current)
            elif current in list_keys:
                lists[current].append((number, stripped))
            continue
        key, colon, value = stripped.partition(":")
        key, value = key.strip(), value.strip()
        if not colon:
            state.bad(number, "not a key: value line")
            current = None
            continue
        if key not in list_keys and key not in scalar_keys:
            state.bad(number, "unknown key %s" % short(key))
            current = "?"
            continue
        if key in seen:
            state.bad(number, "the key %s is given twice" % key)
            current = "?"
            continue
        seen.add(key)
        current = key
        if key in list_keys:
            lists[key] = []
            if value:
                state.bad(number, "%s is a list: write its items on indented lines" % key)
        elif not value:
            state.bad(number, "%s needs a value" % key)
        else:
            scalars[key] = (number, value)
    return scalars, lists


def parse_readers(state, items):
    """The Readers of a plan's ``readers`` items: ``<name> | <command>``, then optionally
    ``not-blind`` and ``cost <n>`` in either order. A live command must split into words
    and name an absolute path or a program looked up on PATH."""
    readers, names = [], set()
    for number, item in items:
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) < 2:
            state.bad(number, "a reader is written: name | command")
            continue
        name, command = parts[0], parts[1]
        if not NAME.match(name):
            state.bad(number, "a name holds letters, digits and - only: %s" % short(name))
            continue
        if name in names:
            state.bad(number, "the reader %s is named twice" % name)
            continue
        not_blind, cost, ok = False, 1, True
        seen_cost = False
        for extra in parts[2:]:
            if extra == "not-blind" and not not_blind:
                not_blind = True
            elif extra.startswith("cost ") and not seen_cost:
                seen_cost = True
                got = state.integer(number, "cost", extra[5:].strip())
                if got is None:
                    ok = False
                else:
                    cost = got
            else:
                state.bad(number, "a reader's extra field is not-blind or cost <n>, once "
                          "each: %s" % short(extra))
                ok = False
        if command != FAKE:
            try:
                words = shlex.split(command)
                if not words:
                    raise ValueError("empty")
            except ValueError:
                state.bad(number, "the reader command cannot be split into words")
                ok = False
            else:
                if "/" in words[0] and not os.path.isabs(words[0]):
                    state.bad(number, "the reader program must be an absolute path or a "
                              "name looked up on PATH: %s" % short(words[0]))
                    ok = False
        if ok:
            names.add(name)
            readers.append(Reader(name, command, not_blind, cost if command != FAKE else 1))
    return readers


def rule_extras(state, number, extras, reads, strengths=()):
    """(strength, read number, ok) from the fields after a fake-reader rule: ``[| strength]
    [| read <k>]`` (``[| read <k>]`` alone when ``strengths`` is empty). Either value is None
    when absent. ``ok`` is False, with a problem recorded, on a field that is neither or a
    read outside 1 to ``reads``."""
    strength, on_read = None, None
    for index, extra in enumerate(extras):
        match = READ_K.match(extra)
        if extra in strengths and strength is None and on_read is None and index == 0:
            strength = extra
        elif match and on_read is None and index == len(extras) - 1:
            on_read = int(match.group(1))
        else:
            what = "come [| strength] [| read <k>]" if strengths else "comes [| read <k>]"
            state.bad(number, "after the rule %s: %s" % (what, short(extra)))
            return None, None, False
    if on_read is not None and not 1 <= on_read <= reads:
        state.bad(number, "read %d is outside the arm's reads (1 to %d)" % (on_read, reads))
        return None, None, False
    return strength, on_read, True


# ------------------------------------------------------------------ files and hashes

class Unreadable(Exception):
    pass


class RunFolderError(Exception):
    """A file in the run folder could not be read or written. ``name`` is relative to the run
    folder and ``line`` is the one line the command prints (after ``cannot run: ``)."""

    def __init__(self, action, name, reason):
        Exception.__init__(self, "cannot %s %s: %s" % (action, name, reason))
        self.action = action
        self.name = name
        self.reason = reason

    @property
    def line(self):
        return "cannot %s %s: %s" % (self.action, show(self.name), show(self.reason))


def reason_of(exc):
    return getattr(exc, "strerror", None) or exc.__class__.__name__


def relative(folder, path):
    return os.path.relpath(path, folder)


def write_new(folder, path, data, taken=False):
    """Create ``path`` (which must not exist) holding ``data``, text or bytes. Any OSError is a
    RunFolderError, except that with ``taken`` a name already in use is raised as it is."""
    try:
        if isinstance(data, bytes):
            with open(path, "xb") as handle:
                handle.write(data)
        else:
            with open(path, "x", encoding="utf-8", newline="") as handle:
                handle.write(data)
    except FileExistsError:
        if taken:
            raise
        raise RunFolderError("write", relative(folder, path), "File exists")
    except OSError as exc:
        raise RunFolderError("write", relative(folder, path), reason_of(exc))


def read_bytes(folder, path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise RunFolderError("read", relative(folder, path), reason_of(exc))


def listdir(folder, path):
    try:
        return os.listdir(path)
    except OSError as exc:
        raise RunFolderError("read", relative(folder, path), reason_of(exc))


def folder_of(plan_path):
    return os.path.dirname(os.path.abspath(plan_path))


def sha256_file(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except (OSError, ValueError):
        return None


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def unique_inputs(items):
    """The (label, path) pairs with each label kept once, in first-seen order."""
    seen = set()
    unique = []
    for label, path in items:
        if label not in seen:
            seen.add(label)
            unique.append((label, path))
    return unique


def freeze_files(folder):
    return sorted(n for n in listdir(folder, folder) if n.endswith(FREEZE_SUFFIX))


def reply_files(folder):
    """The reply files the run folder holds, as reads/<arm>/<k>/REPLY.txt."""
    found = []
    reads = os.path.join(folder, READS_DIR)
    if os.path.isdir(reads):
        for arm in sorted(listdir(folder, reads)):
            arm_dir = os.path.join(reads, arm)
            if not os.path.isdir(arm_dir):
                continue
            for number in sorted(listdir(folder, arm_dir)):
                if os.path.isfile(os.path.join(arm_dir, number, READ_REPLY)):
                    found.append("%s/%s/%s/%s" % (READS_DIR, arm, number, READ_REPLY))
    return found


def freeze(plan_path, parse, inputs, prompt_digest):
    """Read the plan with ``parse``, hash it and every input ``inputs(plan, plan_path)`` names
    (ordered (label, path) pairs), and write the freeze file beside it. Every plan problem is
    found here. ``prompt_digest`` is the sha256 of the command's built-in prompt."""
    try:
        return _freeze(plan_path, parse, inputs, prompt_digest)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def _freeze(plan_path, parse, inputs, prompt_digest):
    try:
        plan = parse(plan_path)
    except PlanError as exc:
        return Result(2, False, error="\n".join(exc.problems))
    problems = []
    folder = folder_of(plan_path)
    hashes = []
    for label, path in inputs(plan, plan_path):
        digest = sha256_file(path) if os.path.isfile(path) else None
        if digest is None:
            problems.append("missing input: %s" % show(label))
        hashes.append((label, digest))
    hashes.append((PROMPT_LABEL, prompt_digest))
    for name in freeze_files(folder):
        problems.append("a freeze file already exists: %s" % show(name))
    for name in reply_files(folder):
        problems.append("the run folder already holds a reply: %s" % show(name))
    if problems:
        return Result(2, False, error="\n".join(problems))
    name = os.path.basename(plan_path) + FREEZE_SUFFIX
    write_new(folder, os.path.join(folder, name),
              "".join("%s  %s\n" % (digest, label) for label, digest in hashes))
    return Result(0, True, text="freeze written: %s\n" % show(name))


def read_freeze(path):
    """The freeze file's (label, digest) pairs, in file order."""
    entries = []
    with open(path, encoding="utf-8") as handle:
        for line in handle.read().split("\n"):
            if line and not line.startswith("#") and "  " in line:
                digest, label = line.split("  ", 1)
                entries.append((label, digest))
    return entries


def verify(plan_path, parse, inputs, prompt_digest, with_prompt):
    """Check the freeze against the files. Returns (plan or None, problems, recorded hashes
    by label, hash of the freeze file). The plan is parsed only when its own hash matches
    the freeze, so a plan edited after the freeze is named and never read."""
    folder = folder_of(plan_path)
    freeze_path = plan_path + FREEZE_SUFFIX
    freeze_name = os.path.basename(freeze_path)
    if not os.path.isfile(freeze_path):
        return None, ["no freeze file: %s" % show(freeze_name)], {}, None
    try:
        entries = read_freeze(freeze_path)
    except (OSError, UnicodeDecodeError):
        return None, ["cannot read the freeze file: %s" % show(freeze_name)], {}, None
    recorded = dict(entries)
    freeze_hash = sha256_file(freeze_path)
    plan_label = os.path.basename(plan_path)
    problems = []

    def compare(label, digest):
        if label == PROMPT_LABEL:
            if with_prompt and digest != prompt_digest:
                problems.append("changed since the freeze: %s" % show(label))
            return
        path = os.path.join(folder, label)
        now = sha256_file(path) if os.path.isfile(path) else None
        if now is None:
            problems.append("missing input: %s" % show(label))
        elif now != digest:
            problems.append("changed since the freeze: %s" % show(label))

    plan_now = sha256_file(plan_path) if os.path.isfile(plan_path) else None
    if plan_label not in recorded or plan_now != recorded[plan_label]:
        if plan_label not in recorded:
            problems.append("not covered by the freeze: %s" % show(plan_label))
        for label, digest in entries:
            compare(label, digest)
        return None, problems, recorded, freeze_hash
    try:
        plan = parse(plan_path)
    except PlanError as exc:
        return None, list(exc.problems), recorded, freeze_hash
    expected = inputs(plan, plan_path)
    for label, _path in expected:
        if label not in recorded:
            problems.append("not covered by the freeze: %s" % show(label))
        else:
            compare(label, recorded[label])
    if PROMPT_LABEL not in recorded:
        if with_prompt:
            problems.append("not covered by the freeze: %s" % PROMPT_LABEL)
    else:
        compare(PROMPT_LABEL, recorded[PROMPT_LABEL])
    labels = set(label for label, _path in expected) | set([PROMPT_LABEL])
    for label in sorted(recorded):
        if label not in labels:
            problems.append("the freeze names a file the plan does not: %s" % show(label))
    return plan, problems, recorded, freeze_hash


def run_folder_problems(folder):
    """One problem for each of the run's files that already exists in the folder."""
    problems = []
    for name in (READS_DIR, KEY_FILE, RUN_LOG):
        if os.path.exists(os.path.join(folder, name)):
            problems.append("the run folder already holds a run: %s" % name)
    return problems


# ------------------------------------------------------------------ text

def collapsed_lines(text):
    """Lines with each run of spaces and tabs made one space, stripped, blanks dropped."""
    lines = []
    for raw in LINE_BREAK.split(text):
        line = _SPACES.sub(" ", raw).strip()
        if line:
            lines.append(line)
    return lines


def changed_lines(first, second):
    """(mark, line) for every line in a non-equal opcode: "-" from first, "+" from second."""
    matcher = difflib.SequenceMatcher(None, first, second, autojunk=False)
    found = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        found.extend(("-", line) for line in first[i1:i2])
        found.extend(("+", line) for line in second[j1:j2])
    return found


def read_text(path):
    """The text of a version or posting file; a PDF goes through pdf_text."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (OSError, ValueError):
        raise Unreadable("cannot read")
    if path.lower().endswith(".pdf"):
        try:
            return pdf_text.pdf_text(path)
        except pdf_text.PdfTextError as exc:
            raise Unreadable("pdftotext " + exc.reason)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise Unreadable("not valid UTF-8")


def text_of(folder, label):
    """The text of an input named relative to the run folder; an unreadable one is a
    RunFolderError."""
    try:
        return read_text(os.path.join(folder, label))
    except Unreadable as exc:
        raise RunFolderError("read", label, str(exc))


# ------------------------------------------------------------------ the reply format

def split_fields(text, labels):
    """(fields, first lines, repeated): a field starts a line as ``FIELD: value``
    (case-sensitive, one of ``labels``) and runs to the next line that starts with a field
    name; text before the first field is ignored. ``fields`` maps each label to its stripped
    value, ``first lines`` to the rest of the line the label starts, and ``repeated`` lists
    the labels that appear more than once."""
    label_line = re.compile(r"^(%s):(.*)$" % "|".join(labels))
    parts = {}
    repeated = []
    current = None
    for line in LINE_BREAK.split(text):
        match = label_line.match(line)
        if match:
            label = match.group(1)
            if label in parts:
                repeated.append(label)
                current = None
            else:
                parts[label] = [match.group(2)]
                current = label
        elif current is not None:
            parts[current].append(line)
    fields = dict((k, "\n".join(v).strip()) for k, v in parts.items())
    first = dict((k, v[0]) for k, v in parts.items())
    return fields, first, repeated


def whole_number(value):
    """The integer a score field holds, or None when it is not one."""
    if _WHOLE.match(value):
        return int(value)
    return None


def prior_flag(fields):
    """The flag for a reply's PRIOR: None only when it is exactly ``nothing``."""
    prior = fields.get("PRIOR")
    if prior is None:
        return "PRIOR missing"
    if prior != "nothing":
        return "PRIOR is not nothing: %s" % prior
    return None


# ------------------------------------------------------------------ live readers and the reads

def costs_of(readers):
    return dict((reader.name, reader.cost) for reader in readers)


def live_preview(readers, spend_ceiling, planned):
    """The text printed by a run that holds live readers and was not given --live."""
    costs = costs_of(readers)
    lines = ["live readers are configured: nothing was started and no reply was written; "
             "add --live to run them"]
    for reader in readers:
        if reader.kind == "live":
            lines.append("reader %s: %s (cost %d per read)"
                         % (reader.name, show(reader.command), reader.cost))
    lines.append("planned reads: %d" % len(planned))
    lines.append("estimated spend: %d (the sum of the planned reads' declared costs; "
                 "the tool cannot see real spend)" % sum(costs[r.reader] for r in planned))
    lines.append("spend ceiling: %s" % ("none" if spend_ceiling is None else spend_ceiling))
    return "".join("%s\n" % line for line in lines)


def live_read(folder, reader, where, timeout):
    """Run one live read in its folder. Returns None for a read that gave a reply, else the
    reason it failed. A reader that has written REPLY.txt or STDERR.txt itself is a failed
    read: the tool writes neither file for it and leaves what the reader wrote as it is."""
    try:
        done = ab_reader_command.run_reader_command(shlex.split(reader.command), where,
                                                    timeout)
    except ab_reader_command.ReaderCommandError as exc:
        return {"not found": "reader command not found",
                "timed out": "timed out"}.get(exc.reason, "reader command could not run")
    for name in (READ_REPLY, READ_STDERR):
        if os.path.lexists(os.path.join(where, name)):
            return "the reader wrote %s into its folder" % name
    write_new(folder, os.path.join(where, READ_STDERR), done.stderr)
    if done.returncode != 0:
        return "exit status %d" % done.returncode
    write_new(folder, os.path.join(where, READ_REPLY), done.stdout)
    return None


def run_reads(folder, planned, readers, spend_ceiling, read_timeout, key_text, prepare,
              fake_reply):
    """Write the key, then run every planned read in order, and always write the run log.

    Each read has ``arm``, ``number``, ``reader`` and ``id``. ``prepare(where, read)`` writes
    the read folder's input files; ``fake_reply(read)`` is the fake reader's reply text. The
    spend ceiling stops the run between reads once the tally of declared costs reaches it.
    Returns the escaped ``stopped`` reason when the loop ended early for any reason other than
    the ceiling, else None; an interrupt or unexpected error is re-raised after the log."""
    costs = costs_of(readers)
    by_name = dict((reader.name, reader) for reader in readers)
    write_new(folder, os.path.join(folder, KEY_FILE), key_text)
    key_hash = sha256_text(key_text)
    spent = 0
    ran = 0
    cut = False
    failures = []
    stopped = None
    try:
        for read in planned:
            if spend_ceiling is not None and spent >= spend_ceiling:
                cut = True
                break
            where = os.path.join(folder, READS_DIR, read.arm, str(read.number))
            try:
                os.makedirs(where)
            except OSError as exc:
                raise RunFolderError("write", relative(folder, where), reason_of(exc))
            prepare(where, read)
            reader = by_name[read.reader]
            if reader.kind == "fake":
                write_new(folder, os.path.join(where, READ_REPLY), fake_reply(read))
            else:
                reason = live_read(folder, reader, where, read_timeout)
                if reason is not None:
                    failures.append((read.id, reason))
            spent += costs[read.reader]
            ran += 1
    except RunFolderError as exc:
        stopped = exc.line
    except BaseException as exc:
        stopped = ("interrupted" if isinstance(exc, KeyboardInterrupt)
                   else "an unexpected error (%s)" % exc.__class__.__name__)
        raise
    finally:
        # The run log is always written once the key is: with a stop, a last line says why.
        lines = ["planned reads: %d" % len(planned), "reads run: %d" % ran,
                 "spend: %d" % spent,
                 "spend ceiling: %s" % ("none" if spend_ceiling is None else spend_ceiling),
                 "cut: %s" % ("yes" if cut else "no"),
                 "key sha256: %s" % key_hash]
        lines += ["failure %s: %s" % (read_id, reason) for read_id, reason in failures]
        if stopped is not None:
            lines.append("stopped: %s" % stopped)
        write_new(folder, os.path.join(folder, RUN_LOG),
                  "".join("%s\n" % line for line in lines))
    return stopped


def scored_after_run(stopped, score_and_write):
    """The result of scoring after the reads: a run that stopped early still scores what it
    has, and a scoring that then fails reports both."""
    if stopped is None:
        return score_and_write()
    try:
        return score_and_write()
    except RunFolderError as exc:
        return Result(2, False, error="%s\n%s" % (stopped, exc.line))


# ------------------------------------------------------------------ scoring

class KeyParseError(Exception):
    pass


_WORDS = {3: "three", 4: "four"}


class Record(object):
    """One read at scoring time: ``status`` is "valid", "failed" or "not run"."""

    def __init__(self, read, status, reply=None, reason=None):
        self.read = read
        self.status = status
        self.reply = reply
        self.reason = reason


def parse_key(data, width):
    """The rows of a key file's bytes, each a list of ``width`` fields whose first is a read
    id such as ``c1/3``. Raises KeyParseError, saying which line."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise KeyParseError("not valid UTF-8")
    rows = []
    for number, line in enumerate(text.split("\n"), 1):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != width:
            raise KeyParseError("line %d does not hold %s fields separated by tabs"
                                % (number, _WORDS.get(width, str(width))))
        arm, slash, count = fields[0].rpartition("/")
        if not arm or not slash or not INTEGER.match(count):
            raise KeyParseError("line %d does not start with a read such as c1/3" % number)
        rows.append([arm, int(count)] + fields[1:])
    return rows


def load_key(folder, width):
    data = read_bytes(folder, os.path.join(folder, KEY_FILE))
    try:
        return parse_key(data, width)
    except KeyParseError as exc:
        raise RunFolderError("parse", KEY_FILE, str(exc))


def load_log(folder):
    log = {}
    data = read_bytes(folder, os.path.join(folder, RUN_LOG))
    for line in data.decode("utf-8", errors="replace").split("\n"):
        if ": " in line:
            label, value = line.split(": ", 1)
            log[label] = value
    return log


def key_problems(folder, width):
    """The key is checked against the hash the run log recorded, and must parse."""
    recorded = load_log(folder).get("key sha256")
    if recorded is None:
        return ["no key sha256 line in %s" % RUN_LOG]
    data = read_bytes(folder, os.path.join(folder, KEY_FILE))
    if hashlib.sha256(data).hexdigest() != recorded:
        return ["changed since the run: %s" % KEY_FILE]
    try:
        parse_key(data, width)
    except KeyParseError as exc:
        return ["cannot parse %s: %s" % (KEY_FILE, exc)]
    return []


def score(plan_path, parse, inputs, prompt_digest, key_width, score_and_write):
    """Score the replies in the run folder again, against the frozen plan: the checks every
    ``score`` subcommand makes, then ``score_and_write(plan, recorded, freeze_hash)``."""
    try:
        plan, problems, recorded, freeze_hash = verify(plan_path, parse, inputs,
                                                       prompt_digest, with_prompt=False)
        folder = folder_of(plan_path)
        if plan is not None and not problems:
            for name in (KEY_FILE, RUN_LOG):
                if not os.path.isfile(os.path.join(folder, name)):
                    problems.append("the run folder holds no %s" % name)
        if plan is not None and not problems:
            problems += key_problems(folder, key_width)
        if problems:
            return Result(2, False, error="\n".join(problems))
        return score_and_write(plan, recorded, freeze_hash)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def records(folder, reads, unrun, failures, parse_reply):
    """One Record per planned read: failed from the run log, not run (when the run was cut
    or stopped) or missing, else parsed with ``parse_reply`` into valid or failed."""
    found = []
    for read in reads:
        path = os.path.join(folder, READS_DIR, read.arm, str(read.number), READ_REPLY)
        if read.id in failures:
            found.append(Record(read, "failed", reason=failures[read.id]))
            continue
        if not os.path.isfile(path):
            if unrun:
                found.append(Record(read, "not run"))
            else:
                found.append(Record(read, "failed", reason="no reply file"))
            continue
        text = read_bytes(folder, path).decode("utf-8", errors="replace")
        reply = parse_reply(text)
        if reply.failure:
            found.append(Record(read, "failed", reply, reply.failure))
        else:
            found.append(Record(read, "valid", reply))
    return found


def log_failures(log):
    return dict((label[len("failure "):], value) for label, value in log.items()
                if label.startswith("failure "))


def percent(part, whole):
    return "%.0f%%" % (100.0 * part / whole)


def mean(total, count):
    return "%.2f" % (float(total) / count)


def finish_result(folder, out, found, log, stopped):
    """Append the tail every result ends with (spend, failed reads, the cut, a stop and the
    exit status), write the next numbered result file, and return the Result."""
    problems = []
    cut = log.get("cut") == "yes"
    out.append("spend tally: %s (a tally of declared costs, not measured spend); ceiling: %s"
               % (show(str(log.get("spend"))), show(str(log.get("spend ceiling")))))
    failed = [x for x in found if x.status == "failed"]
    out.append("failed reads: %d" % len(failed))
    for x in failed:
        line = "failed read %s: %s" % (show(x.read.id), show(x.reason))
        out.append(line)
        problems.append(line)
    if cut:
        line = "cut: ran %s of %s planned reads at spend ceiling %s" % (
            show(str(log.get("reads run"))), show(str(log.get("planned reads"))),
            show(str(log.get("spend ceiling"))))
        problems.append(line)
    else:
        line = "cut: no"
    out.append(line)
    if stopped is not None:
        line = "stopped: %s" % show(stopped)
        out.append(line)
        problems.append(line)

    exit_code = 2 if stopped is not None else 1 if (failed or cut) else 0
    out.append("exit status: %d" % exit_code)
    text = "".join(line + "\n" for line in out)
    number = 1
    while True:
        path = os.path.join(folder, "%s%d.txt" % (RESULT_STEM, number))
        try:
            write_new(folder, path, text, taken=True)
            break
        except FileExistsError:
            number += 1
    return Result(exit_code, True, text=text, error="\n".join(problems),
                  stopped=None if stopped is None else show(stopped))
