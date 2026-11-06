"""Reader panel: blind lens reads of one version, gated by an anchored rubric.

The behaviour is stated in docs/specs/reader-panel.md (revision 1). In short: freeze a plan and
its inputs by hash; for each lens (a reader role, given as a prompt file) read two planted
anchor documents, one deliberately strong and one deliberately weak, and then the version
under test; gate each lens on whether it put the strong anchor at or above one threshold and
the weak anchor at or below another; and score the version's reads of each counted lens
against the frozen rules. Every function that does work returns a Result, as ``ab`` does.

This module reads the plan file (``parse``) and runs the built-in fake reader inside the
tool. A live reader (a command the user names) is started only by ``ab_reader_command``,
through the harness it shares with ``ab`` (``reader_harness``).
"""

import hashlib
import os
import re
from fractions import Fraction

from career_track_record import reader_harness as harness

# File names inside a read folder, and in the run folder. Every use goes through these.
READ_DOCUMENT = "DOCUMENT.txt"
READ_LENS = "LENS.txt"
READ_POSTING = harness.READ_POSTING
READ_PROMPT = harness.READ_PROMPT
READ_REPLY = harness.READ_REPLY
READ_STDERR = harness.READ_STDERR
READS_DIR = harness.READS_DIR
KEY_FILE = harness.KEY_FILE
RUN_LOG = harness.RUN_LOG
RESULT_STEM = harness.RESULT_STEM
FREEZE_SUFFIX = harness.FREEZE_SUFFIX
PROMPT_LABEL = harness.PROMPT_LABEL
FAKE = harness.FAKE
DEFAULT_READ_TIMEOUT = harness.DEFAULT_READ_TIMEOUT

_show = harness.show

Result = harness.Result
Reader = harness.Reader
PlanError = harness.PlanError
Unreadable = harness.Unreadable
RunFolderError = harness.RunFolderError
collapsed_lines = harness.collapsed_lines
changed_lines = harness.changed_lines
read_text = harness.read_text

# The three documents each lens reads, in the order they are read. The anchors come first,
# so that a run cut by the spend ceiling still has its gate.
STRONG = "strong"
WEAK = "weak"
VERSION = "version"
DOCUMENTS = (STRONG, WEAK, VERSION)
ANCHORS = (STRONG, WEAK)
# Words a lens may not be named, because the plan's fake-reader and rules items use them.
RESERVED = ("all", "overall") + DOCUMENTS

LABELS = ("READ", "PRIOR", "SCORE", "STRENGTHS", "DOUBTS", "UNDERSOLD", "OVEREXPLAINED",
          "OWNED", "FLAG-FIXES")
FREE_TEXT_FIELDS = ("STRENGTHS", "DOUBTS", "UNDERSOLD", "OVEREXPLAINED", "OWNED",
                    "FLAG-FIXES")
# A free-text field is flagged when it holds anything but this word.
NONE = "none"
VERDICTS = ("PASS", "FAIL")

PROMPT = """You are reading one career document for a job, in the role that
LENS.txt gives you. You know nothing about the candidate beyond what is
in these files. Do not guess or use outside knowledge.

Your folder holds four files:
  LENS.txt      the role you read in, and what that role looks for
  POSTING.txt   the job posting
  DOCUMENT.txt  the document to read
  PROMPT.txt    this text

Nothing tells you whether this document is a draft, a final version or a
sample. Judge it on its own, against the posting, in your role.

Read LENS.txt, then the posting, then the document. Answer on standard
output only. Write these nine fields, in this order, each starting its
own line as FIELD: value. No bullets, bold, indentation or text before
the first field or after the last. A value may continue on later lines;
the next field name starts a new line.

READ: anything; this value is not checked
PRIOR: what you knew about the candidate before reading. If nothing, write exactly: nothing
SCORE: a whole number, as digits only, on the scale LENS.txt gives
STRENGTHS: what in the document works for this role; write exactly `none` if you have nothing material.
DOUBTS: what made you doubt the candidate; write exactly `none` if you have nothing material.
UNDERSOLD: what the candidate has but did not make the most of; write exactly `none` if you have nothing material.
OVEREXPLAINED: what took more space or words than it earned; write exactly `none` if you have nothing material.
OWNED: what the candidate clearly did or led themselves; write exactly `none` if you have nothing material.
FLAG-FIXES: changes you would suggest, as text only; nothing is applied; write exactly `none` if you have nothing material.
"""


# ------------------------------------------------------------------ the plan model

class Lens(object):
    """A lens: a reader role, read from a plain-text prompt file. ``arm`` is l1, l2 and so
    on in plan order."""

    def __init__(self, name, path, arm, max=None):
        self.name = name
        self.path = path
        self.arm = arm
        self.max = max


class FakeRule(object):
    """One rule of the fake reader. ``lenses`` names the arms it applies to (l1, l2, ...)
    and ``documents`` the documents (strong, weak, version); None means every one.
    ``on_reads`` is a set of read numbers counted across the lens."""

    KINDS = ("score", "score-containing", "write", "omit")

    def __init__(self, kind, score=None, text=None, field=None, lenses=None,
                 documents=None, on_reads=None):
        if kind not in self.KINDS:
            raise ValueError("unknown rule kind %r" % (kind,))
        if field is not None and field not in LABELS:
            raise ValueError("unknown field %r" % (field,))
        if documents is not None and not set(documents) <= set(DOCUMENTS):
            raise ValueError("unknown document in %r" % (documents,))
        self.kind = kind
        self.score = score
        self.text = text
        self.field = field
        self.lenses = None if lenses is None else frozenset(lenses)
        self.documents = None if documents is None else frozenset(documents)
        self.on_reads = None if on_reads is None else frozenset(on_reads)

    @classmethod
    def score_of(cls, score, **mods):
        return cls("score", score=score, **mods)

    @classmethod
    def score_containing(cls, text, score, **mods):
        return cls("score-containing", text=text, score=score, **mods)

    @classmethod
    def write(cls, field, text, **mods):
        return cls("write", field=field, text=text, **mods)

    @classmethod
    def omit(cls, field, **mods):
        return cls("omit", field=field, **mods)


class Clause(object):
    """One clause of a rule, counted over valid version reads: ``kind`` is "at least" or
    "at most" (a score against ``threshold``), or "flagged" or "not flagged" (of ``field``).
    It holds in K of N reads (n given) or in K or more (n is None)."""

    def __init__(self, kind, k, n=None, threshold=None, field=None):
        self.kind = kind
        self.k = k
        self.n = n
        self.threshold = threshold
        self.field = field

    def test(self):
        if self.kind in ("at least", "at most"):
            return "score %s %d" % (self.kind, self.threshold)
        return "%s %s" % (self.field, self.kind)

    def text(self):
        if self.n is None:
            return "%s in %d or more" % (self.test(), self.k)
        return "%s in %d of %d" % (self.test(), self.k, self.n)

    def holds_for(self, reply):
        if self.kind == "at least":
            return reply.score >= self.threshold
        if self.kind == "at most":
            return reply.score <= self.threshold
        flagged = self.field in reply.flagged
        return flagged if self.kind == "flagged" else not flagged


class Rule(object):
    """A pass condition for one lens (``lens`` is its arm, l1, l2, ...) or for the whole
    panel (``lens`` is None, written ``overall``). ``clauses`` is an ordered list of
    (verdict, Clause) with verdict PASS or FAIL; the first that holds decides, and when none
    holds the verdict is INCONCLUSIVE. ``name`` is r1, r2, ... in plan order."""

    def __init__(self, name, lens, clauses=(), null_share=None, null_share_text=None):
        self.name = name
        self.lens = lens
        self.clauses = list(clauses)
        self.null_share = null_share
        self.null_share_text = null_share_text


class Plan(object):
    """The plan as an object. ``anchors`` maps ``strong`` and ``weak`` to a path, ``lenses``
    is an ordered list of Lens. Relative paths are relative to the folder that holds the
    plan file."""

    def __init__(self, posting, version, anchors, lenses, readers, strong_at_least,
                 weak_at_most, fake_rules=(), reads_per_reader=3,
                 anchor_reads_per_reader=1, rules=(), spend_ceiling=None, amends=None,
                 read_timeout=DEFAULT_READ_TIMEOUT, sidedness="two"):
        self.posting = posting
        self.version = version
        self.anchors = dict(anchors)
        self.lenses = list(lenses)
        self.readers = list(readers)
        self.strong_at_least = strong_at_least
        self.weak_at_most = weak_at_most
        self.fake_rules = list(fake_rules)
        self.reads_per_reader = reads_per_reader
        self.anchor_reads_per_reader = anchor_reads_per_reader
        self.rules = list(rules)
        self.spend_ceiling = spend_ceiling
        self.amends = amends
        self.read_timeout = read_timeout
        self.sidedness = sidedness

    def document_path(self, document):
        if document == VERSION:
            return self.version
        return self.anchors[document]

    def reads_per_document(self, document):
        each = self.reads_per_reader if document == VERSION else self.anchor_reads_per_reader
        return len(self.readers) * each

    def reads_per_lens(self):
        return sum(self.reads_per_document(document) for document in DOCUMENTS)

    def lens_of(self, arm):
        for lens in self.lenses:
            if lens.arm == arm:
                return lens
        return None

    def live_readers(self):
        return [r for r in self.readers if r.kind == "live"]


# ------------------------------------------------------------------ the plan file

_LIST_KEYS = ("anchors", "lenses", "readers", "rules", "fake-reader")
_SCALAR_KEYS = ("posting", "version", "reads-per-reader", "anchor-reads-per-reader",
                "anchor-strong-at-least", "anchor-weak-at-most", "spend-ceiling", "amends",
                "read-timeout", "sidedness")
_NAME = harness.NAME
_CLAUSE = re.compile(r"(PASS|FAIL) if (?:score at (least|most) (-?[0-9]+)"
                     r"|([A-Z-]+) (flagged|not flagged)) in "
                     r"(?:([0-9]+) of ([0-9]+)|([0-9]+) or more)\Z")
_QUOTED = harness.QUOTED
_short = harness.short


def parse(path):
    """Read a plan file and return a Plan. Raises PlanError, naming each problem with the
    plan line number where there is one."""
    return parse_text(harness.plan_text(path))


def parse_text(text):
    """The work of ``parse``, on the text of a plan."""
    state = harness.ParseState()
    scalars, lists = harness.structure(state, text, _LIST_KEYS, _SCALAR_KEYS)

    # scalars
    posting = scalars["posting"][1] if "posting" in scalars else None
    version = scalars["version"][1] if "version" in scalars else None
    reads_per_reader = 3
    if "reads-per-reader" in scalars:
        number, value = scalars["reads-per-reader"]
        got = state.integer(number, "reads-per-reader", value, minimum=1)
        reads_per_reader = got if got is not None else 3
    anchor_reads = 1
    if "anchor-reads-per-reader" in scalars:
        number, value = scalars["anchor-reads-per-reader"]
        got = state.integer(number, "anchor-reads-per-reader", value, minimum=1)
        anchor_reads = got if got is not None else 1
    strong_at_least = weak_at_most = None
    if "anchor-strong-at-least" in scalars:
        number, value = scalars["anchor-strong-at-least"]
        strong_at_least = state.signed(number, "anchor-strong-at-least", value)
    if "anchor-weak-at-most" in scalars:
        number, value = scalars["anchor-weak-at-most"]
        weak_at_most = state.signed(number, "anchor-weak-at-most", value)
    if (strong_at_least is not None and weak_at_most is not None
            and strong_at_least <= weak_at_most):
        state.bad(scalars["anchor-strong-at-least"][0],
                  "anchor-strong-at-least must be greater than anchor-weak-at-most")
    ceiling = None
    if "spend-ceiling" in scalars:
        number, value = scalars["spend-ceiling"]
        ceiling = state.integer(number, "spend-ceiling", value)
    timeout = DEFAULT_READ_TIMEOUT
    if "read-timeout" in scalars:
        number, value = scalars["read-timeout"]
        got = state.integer(number, "read-timeout", value)
        timeout = got if got is not None else DEFAULT_READ_TIMEOUT
    amends = scalars["amends"][1] if "amends" in scalars else None
    sidedness = "two"
    if "sidedness" in scalars:
        number, value = scalars["sidedness"]
        if value in ("two", "greater", "less"):
            sidedness = value
        else:
            state.bad(number, "sidedness is two, greater or less")

    # anchors
    anchors = {}
    for number, item in lists.get("anchors", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) != 2 or parts[0] not in ANCHORS:
            state.bad(number, "an anchor is written: strong | file, or weak | file")
        elif parts[0] in anchors:
            state.bad(number, "the anchor %s is named twice" % parts[0])
        else:
            anchors[parts[0]] = parts[1]

    # lenses
    lenses, lens_names = [], []
    for number, item in lists.get("lenses", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        lens_max = None
        if len(parts) == 3 and parts[2].startswith("max "):
            text_max = parts[2][len("max "):]
            if not re.fullmatch(r"-?[0-9]+", text_max):
                state.bad(number, "a lens's max is a whole number: %s" % _short(text_max))
                continue
            lens_max = int(text_max)
            if strong_at_least is not None and lens_max < strong_at_least:
                state.bad(number, "max %d is below anchor-strong-at-least (%d)"
                          % (lens_max, strong_at_least))
                continue
            parts = parts[:2]
        if len(parts) != 2:
            state.bad(number, "a lens is written: name | file")
        elif not _NAME.match(parts[0]):
            state.bad(number, "a name holds letters, digits and - only: %s" % _short(parts[0]))
        elif parts[0] in RESERVED:
            state.bad(number, "a lens may not be named %s" % parts[0])
        elif parts[0] in lens_names:
            state.bad(number, "the lens %s is named twice" % parts[0])
        else:
            lens_names.append(parts[0])
            lenses.append(Lens(parts[0], parts[1], "l%d" % (len(lenses) + 1), max=lens_max))
    arms = dict((lens.name, lens.arm) for lens in lenses)

    # readers
    readers = harness.parse_readers(state, lists.get("readers", []))

    # rules
    rules = []
    for number, item in lists.get("rules", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        null_share = null_share_text = None
        if len(parts) == 3 and parts[2].startswith("null-share "):
            text_share = parts[2][len("null-share "):]
            found = re.fullmatch(r"([0-9]+)/([0-9]+)", text_share)
            if not found or not 0 < int(found.group(1)) < int(found.group(2)):
                state.bad(number, "null-share is written n/d, strictly between 0 and 1")
                continue
            null_share = Fraction(int(found.group(1)), int(found.group(2)))
            null_share_text = text_share
            parts = parts[:2]
        if len(parts) != 2 or (parts[0] != "overall" and parts[0] not in arms):
            state.bad(number, "a rule is written: <lens> | <rule>, or overall | <rule>, "
                      "with the lens written as in lenses")
            continue
        clauses = _rule_clauses(state, number, parts[1])
        if clauses is not None and strong_at_least is not None:
            for verdict, clause in clauses:
                if (verdict == "PASS" and clause.kind == "at least"
                        and clause.threshold > strong_at_least):
                    state.bad(number, "a PASS clause asks for score at least %d, above "
                              "anchor-strong-at-least (%d): a version cannot be required to "
                              "beat a score the gate did not show the lens can give"
                              % (clause.threshold, strong_at_least))
                    clauses = None
                    break
        if clauses is not None:
            lens = None if parts[0] == "overall" else arms[parts[0]]
            rules.append(Rule("r%d" % (len(rules) + 1), lens, clauses,
                              null_share=null_share, null_share_text=null_share_text))

    # the fake reader
    has_fake = any(r.kind == "fake" for r in readers)
    reads = len(readers) * (2 * anchor_reads + reads_per_reader)
    fake_rules, rule_lines = [], []
    for number, item in lists.get("fake-reader", []):
        rule = _fake_rule(state, number, item, arms, reads)
        if rule is not None:
            fake_rules.append(rule)
            rule_lines.append(number)
    if fake_rules and not has_fake:
        state.bad(rule_lines[0], "fake-reader rules, but the plan has no fake reader")

    # what the plan must have
    if posting is None:
        state.problems.append("the plan names no posting")
    if version is None:
        state.problems.append("the plan names no version")
    for anchor in ANCHORS:
        if anchor not in anchors:
            state.problems.append("the plan names no %s anchor" % anchor)
    if not lenses:
        state.problems.append("the plan names no lens")
    if not readers and not [1 for number, _item in lists.get("readers", [])]:
        state.problems.append("the plan has no reader")
    if strong_at_least is None and "anchor-strong-at-least" not in scalars:
        state.problems.append("the plan sets no anchor-strong-at-least")
    if weak_at_most is None and "anchor-weak-at-most" not in scalars:
        state.problems.append("the plan sets no anchor-weak-at-most")
    if state.problems:
        raise PlanError(state.problems)
    return Plan(posting, version, anchors, lenses, readers, strong_at_least, weak_at_most,
                fake_rules=fake_rules, reads_per_reader=reads_per_reader,
                anchor_reads_per_reader=anchor_reads, rules=rules, spend_ceiling=ceiling,
                amends=amends, read_timeout=timeout, sidedness=sidedness)


def _rule_clauses(state, number, rule):
    """The ordered (verdict, Clause) list of a rule, or None."""
    pieces = rule.split("; ")
    if pieces[-1] != "otherwise INCONCLUSIVE":
        state.bad(number, "a rule ends with: otherwise INCONCLUSIVE")
        return None
    clauses = []
    ok = True
    for piece in pieces[:-1]:
        match = _CLAUSE.match(piece)
        if not match:
            state.bad(number, "a clause is written: PASS (or FAIL) if score at least (or "
                      "at most) <n> in <k> of <m> (or <k> or more), or <FIELD> flagged "
                      "(or not flagged) in <k> of <m> (or <k> or more): %s" % _short(piece))
            ok = False
            continue
        verdict = match.group(1)
        if match.group(4) is not None:
            if match.group(4) not in FREE_TEXT_FIELDS:
                state.bad(number, "not a reply field a rule can test: %s"
                          % _short(match.group(4)))
                ok = False
                continue
            kind, threshold, field = match.group(5), None, match.group(4)
        else:
            kind, threshold, field = "at " + match.group(2), int(match.group(3)), None
        if match.group(8) is not None:
            clauses.append((verdict, Clause(kind, int(match.group(8)), threshold=threshold,
                                            field=field)))
        elif int(match.group(6)) > int(match.group(7)):
            state.bad(number, "%s of %s asks for more reads than it counts"
                      % (match.group(6), match.group(7)))
            ok = False
        else:
            clauses.append((verdict, Clause(kind, int(match.group(6)), int(match.group(7)),
                                            threshold=threshold, field=field)))
    if ok and not clauses:
        state.bad(number, "a rule needs at least one PASS or FAIL clause")
        return None
    return clauses if ok else None


def _fake_rule(state, number, item, arms, reads):
    """One FakeRule from a fake-reader item, ``[<lens> |] [<document> |] <rule>
    [| read <k>]``, or None with a problem recorded."""
    parts = state.fields(number, item)
    if parts is None:
        return None
    lenses = documents = None
    if len(parts) > 1 and (parts[0] == "all" or parts[0] in arms):
        if parts[0] != "all":
            lenses = [arms[parts[0]]]
        parts = parts[1:]
    if len(parts) > 1 and (parts[0] == "all" or parts[0] in DOCUMENTS):
        if parts[0] != "all":
            documents = [parts[0]]
        parts = parts[1:]
    rule_text, extras = parts[0], parts[1:]
    _strength, on_read, ok = harness.rule_extras(state, number, extras, reads)
    if not ok:
        return None
    mods = dict(lenses=lenses, documents=documents,
                on_reads=None if on_read is None else [on_read])
    match = re.match(r"score (-?[0-9]+)\Z", rule_text)
    if match:
        return FakeRule.score_of(int(match.group(1)), **mods)
    match = re.match(r"score containing " + _QUOTED + r" (-?[0-9]+)\Z", rule_text)
    if match:
        return FakeRule.score_containing(match.group(1), int(match.group(2)), **mods)
    match = re.match(r"write " + _QUOTED + r" in ([A-Z-]+)\Z", rule_text)
    if match:
        if match.group(2) not in LABELS:
            state.bad(number, "not a reply field: %s" % _short(match.group(2)))
            return None
        return FakeRule.write(match.group(2), match.group(1), **mods)
    match = re.match(r"omit ([A-Z-]+)\Z", rule_text)
    if match:
        if match.group(1) not in LABELS:
            state.bad(number, "not a reply field: %s" % _short(match.group(1)))
            return None
        return FakeRule.omit(match.group(1), **mods)
    state.bad(number, "not a fake-reader rule: %s" % _short(rule_text))
    return None


# ------------------------------------------------------------------ files and hashes

def prompt_sha256():
    return hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()


def _inputs(plan, plan_path):
    """Ordered (label, absolute path) of the plan file and every input it names: the
    posting, the version, both anchors, every lens file and any amended freeze."""
    folder = harness.folder_of(plan_path)
    items = [(os.path.basename(plan_path), os.path.abspath(plan_path)),
             (plan.posting, os.path.join(folder, plan.posting)),
             (plan.version, os.path.join(folder, plan.version))]
    for anchor in ANCHORS:
        items.append((plan.anchors[anchor], os.path.join(folder, plan.anchors[anchor])))
    for lens in plan.lenses:
        items.append((lens.path, os.path.join(folder, lens.path)))
    if plan.amends is not None:
        items.append((plan.amends, os.path.join(folder, plan.amends)))
    return harness.unique_inputs(items)


def freeze(plan_path):
    """Read the plan, hash it and every input it names, and write the freeze file beside it.
    Every plan problem is found here."""
    return harness.freeze(plan_path, parse, _inputs, prompt_sha256())


def _verify(plan_path, with_prompt):
    return harness.verify(plan_path, parse, _inputs, prompt_sha256(), with_prompt)


# ------------------------------------------------------------------ the document check

def lens_text(path):
    """The text of a lens file: UTF-8 text that is not blank. Raises Unreadable."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (OSError, ValueError):
        raise Unreadable("cannot read")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Unreadable("not valid UTF-8")
    if not text.strip():
        raise Unreadable("the lens file is blank")
    return text


def _document_problems(plan, plan_path):
    """The problems the documents show before any read: one that cannot be read, a blank
    lens, or two of the three documents that do not differ (a gate between two copies of
    one text can tell nothing)."""
    folder = harness.folder_of(plan_path)
    problems = []
    lines = {}
    for document in DOCUMENTS:
        label = plan.document_path(document)
        path = os.path.join(folder, label)
        if not os.path.isfile(path):
            continue  # reported as a missing input by the hash stage
        try:
            lines[document] = collapsed_lines(read_text(path))
        except Unreadable as exc:
            problems.append("cannot read %s: %s" % (_show(label), exc))
    for lens in plan.lenses:
        path = os.path.join(folder, lens.path)
        if os.path.isfile(path):
            try:
                lens_text(path)
            except Unreadable as exc:
                problems.append("cannot read %s: %s" % (_show(lens.path), exc))
    posting = os.path.join(folder, plan.posting)
    if os.path.isfile(posting):
        try:
            read_text(posting)
        except Unreadable as exc:
            problems.append("cannot read %s: %s" % (_show(plan.posting), exc))
    pairs = ((STRONG, WEAK), (STRONG, VERSION), (WEAK, VERSION))
    for first, second in pairs:
        if first in lines and second in lines and not changed_lines(lines[first],
                                                                    lines[second]):
            problems.append("the %s anchor and the %s show no changed line; the gate "
                            "needs documents that differ" % (first, second))
    return problems


# ------------------------------------------------------------------ reply format

class Reply(object):
    """A parsed reply. ``failure`` is None for a valid read, else the reason it failed.
    ``flagged`` holds the free-text fields that say anything but ``none``."""

    def __init__(self):
        self.fields = {}
        self.failure = None
        self.read_id = None
        self.score = None
        self.flagged = ()
        self.prior_flag = None


def parse_reply(text):
    """Parse a reply. A field starts a line as ``FIELD: value`` (case-sensitive) and runs to
    the next line that starts with a field name; text before the first field is ignored."""
    reply = Reply()
    fields, _first, repeated = harness.split_fields(text, LABELS)
    reply.fields = fields
    reply.prior_flag = harness.prior_flag(fields)
    reply.flagged = tuple(f for f in FREE_TEXT_FIELDS if fields.get(f, "") not in ("", NONE))
    if repeated:
        reply.failure = "%s appears twice" % repeated[0]
        return reply
    for label in ("READ", "SCORE"):
        if label not in fields:
            reply.failure = "missing %s" % label
            return reply
    reply.read_id = fields["READ"]
    reply.score = harness.whole_number(fields["SCORE"])
    if reply.score is None:
        reply.failure = "SCORE is not an integer"
    return reply


# ------------------------------------------------------------------ the fake reader

class PlannedRead(object):
    def __init__(self, arm, number, reader, document):
        self.arm = arm
        self.number = number
        self.reader = reader
        self.document = document

    @property
    def id(self):
        return "%s/%d" % (self.arm, self.number)


def _planned_reads(plan):
    """Every read in run order: lens by lens, the strong anchor, the weak anchor, then the
    version; within a document, each reader's reads in turn, numbered across the lens."""
    reads = []
    for lens in plan.lenses:
        number = 0
        for document in DOCUMENTS:
            each = (plan.reads_per_reader if document == VERSION
                    else plan.anchor_reads_per_reader)
            for reader in plan.readers:
                for _ in range(each):
                    number += 1
                    reads.append(PlannedRead(lens.arm, number, reader.name, document))
    return reads


def _fires(rule, read):
    return ((rule.lenses is None or read.arm in rule.lenses)
            and (rule.documents is None or read.document in rule.documents)
            and (rule.on_reads is None or read.number in rule.on_reads))


def fake_reply(read, rules, text):
    """The text of the fake reader's reply to one read of the document ``text``."""
    score = 5
    for rule in rules:
        if not _fires(rule, read):
            continue
        if rule.kind == "score":
            score = rule.score
        elif rule.kind == "score-containing" and rule.text in text:
            score = rule.score
    values = {"READ": read.id, "PRIOR": "nothing", "SCORE": str(score)}
    for label in FREE_TEXT_FIELDS:
        values[label] = NONE
    written = set()
    omitted = set()
    for rule in rules:
        if rule.kind not in ("write", "omit") or not _fires(rule, read):
            continue
        if rule.kind == "omit":
            omitted.add(rule.field)
        elif rule.field in written:
            values[rule.field] += " " + rule.text
        else:
            values[rule.field] = rule.text
            written.add(rule.field)
    return "".join("%s: %s\n" % (label, values[label]) for label in LABELS
                   if label not in omitted)


# ------------------------------------------------------------------ run

def run(plan_path, live=False):
    """Check, key, read and score. Writes the key, the reads, the run log and a result."""
    try:
        return _run(plan_path, live)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def _run(plan_path, live):
    folder = harness.folder_of(plan_path)
    plan, problems, recorded, freeze_hash = _verify(plan_path, with_prompt=True)
    if plan is not None:
        problems += _document_problems(plan, plan_path)
    problems += harness.run_folder_problems(folder)
    if problems:
        return Result(2, False, error="\n".join(problems))
    planned = _planned_reads(plan)
    if plan.live_readers() and not live:
        return Result(0, True, text=harness.live_preview(plan.readers, plan.spend_ceiling,
                                                         planned))
    texts = dict((document, harness.text_of(folder, plan.document_path(document)))
                 for document in DOCUMENTS)
    lens_texts = {}
    for lens in plan.lenses:
        try:
            lens_texts[lens.arm] = lens_text(os.path.join(folder, lens.path))
        except Unreadable as exc:
            raise RunFolderError("read", lens.path, str(exc))
    posting_text = harness.text_of(folder, plan.posting)
    key_text = "".join("%s\t%s\t%s\n" % (r.id, r.reader, r.document) for r in planned)

    def prepare(where, read):
        harness.write_new(folder, os.path.join(where, READ_DOCUMENT), texts[read.document])
        harness.write_new(folder, os.path.join(where, READ_POSTING), posting_text)
        harness.write_new(folder, os.path.join(where, READ_LENS), lens_texts[read.arm])
        harness.write_new(folder, os.path.join(where, READ_PROMPT), PROMPT)

    def reply_of(read):
        return fake_reply(read, plan.fake_rules, texts[read.document])

    stopped = harness.run_reads(folder, planned, plan.readers, plan.spend_ceiling,
                                plan.read_timeout, key_text, prepare, reply_of)
    return harness.scored_after_run(
        stopped, lambda: _score_and_write(plan_path, plan, recorded, freeze_hash))


def score(plan_path):
    """Score the replies in the run folder again, against the frozen plan. Writes a new result."""
    return harness.score(plan_path, parse, _inputs, prompt_sha256(), 3,
                         lambda plan, recorded, freeze_hash: _score_and_write(
                             plan_path, plan, recorded, freeze_hash))


# ------------------------------------------------------------------ scoring

_mean = harness.mean


def _clause_holds(clause, recs):
    """Whether a clause holds over the valid reads ``recs``, and how many of them it is
    true of."""
    count = len([x for x in recs if clause.holds_for(x.reply)])
    if clause.n is None:
        return count >= clause.k, count
    return len(recs) == clause.n and count >= clause.k, count


def _scores_line(label, pairs):
    """A ``scores`` line for (reader, score) pairs, or None when there are none."""
    if not pairs:
        return None
    scores = [s for _r, s in pairs]
    return "%s: scores=%d total=%d mean=%s lowest=%d highest=%d" % (
        label, len(scores), sum(scores), _mean(sum(scores), len(scores)), min(scores),
        max(scores))


def _score_and_write(plan_path, plan, recorded, freeze_hash):
    folder = harness.folder_of(plan_path)
    log = harness.load_log(folder)
    cut = log.get("cut") == "yes"
    stopped = log.get("stopped")
    reads = [PlannedRead(*row) for row in harness.load_key(folder, 3)]
    failures = harness.log_failures(log)
    records = harness.records(folder, reads, cut or stopped is not None, failures,
                              parse_reply)
    not_blind = set(r.name for r in plan.readers if r.not_blind)
    out = []

    out.append("plan sha256: %s" % _show(recorded.get(os.path.basename(plan_path), "unknown")))
    out.append("freeze sha256: %s" % freeze_hash)
    if plan.amends is not None:
        out.append("amended freeze sha256: %s" % _show(recorded.get(plan.amends, "unknown")))
    out.append("prompt sha256: %s" % _show(recorded.get(PROMPT_LABEL, "unknown")))
    out.append("version: %s" % _show(plan.version))
    for anchor in ANCHORS:
        out.append("anchor %s: %s" % (anchor, _show(plan.anchors[anchor])))
    out.append("anchor thresholds: strong at least %d; weak at most %d"
               % (plan.strong_at_least, plan.weak_at_most))
    for lens in plan.lenses:
        out.append("lens %s: %s (%s, sha256 %s)" % (lens.arm, _show(lens.name),
                                                     _show(lens.path),
                                                     _show(recorded.get(lens.path, "unknown"))))
    for r in reads:
        out.append("key %s: reader=%s document=%s" % (_show(r.id), _show(r.reader),
                                                      _show(r.document)))

    for rec in records:
        r = rec.read
        head = "read %s: reader=%s document=%s" % (_show(r.id), _show(r.reader),
                                                   _show(r.document))
        flags = []
        if r.reader in not_blind:
            flags.append("not-blind reader")
        if rec.status == "valid":
            if rec.reply.prior_flag:
                flags.append(_show(rec.reply.prior_flag))
            out.append("%s score=%d flagged=%s flags=%s" % (
                head, rec.reply.score, ",".join(rec.reply.flagged) or "none",
                "; ".join(flags) if flags else "none"))
        elif rec.status == "failed":
            out.append("%s FAILED (%s)" % (head, _show(rec.reason)))
        else:
            out.append("%s not run" % head)

    def valid_in(arm, document, only=None):
        return [x for x in records if x.read.arm == arm and x.read.document == document
                and x.status == "valid" and (only is None or x.read.reader in only)]

    def planned_in(arm, document):
        return [r for r in reads if r.arm == arm and r.document == document]

    # each lens: its reads, its anchor gate, whether it is counted, its scores and flags
    counted = []
    gate_reason = {}
    for lens in plan.lenses:
        arm = lens.arm
        for document in ANCHORS:
            out.append("reads %s %s: valid=%d of %d planned"
                       % (arm, document, len(valid_in(arm, document)),
                          len(planned_in(arm, document))))
        out.append("reads %s version all readers: valid=%d of %d planned"
                   % (arm, len(valid_in(arm, VERSION)), len(planned_in(arm, VERSION))))
        out.append("reads %s version not-blind readers: valid=%d"
                   % (arm, len(valid_in(arm, VERSION, not_blind))))
        strong_recs, weak_recs = valid_in(arm, STRONG), valid_in(arm, WEAK)
        anchor_planned = len(planned_in(arm, STRONG)) + len(planned_in(arm, WEAK))
        anchor_valid = len(strong_recs) + len(weak_recs)
        if anchor_planned == 0 or anchor_valid < anchor_planned:
            out.append("anchor gate %s: not evaluated (%d valid anchor reads of %d planned)"
                       % (arm, anchor_valid, anchor_planned))
            gate_reason[arm] = "the anchor gate was not evaluated on %s" % arm
        else:
            low = ["%s read %s scored %d, below %d" % (STRONG, _show(x.read.id),
                                                       x.reply.score, plan.strong_at_least)
                   for x in strong_recs if x.reply.score < plan.strong_at_least]
            high = ["%s read %s scored %d, above %d" % (WEAK, _show(x.read.id),
                                                        x.reply.score, plan.weak_at_most)
                    for x in weak_recs if x.reply.score > plan.weak_at_most]
            if low or high:
                out.append("anchor gate %s: failed (%s)" % (arm, "; ".join(low + high)))
                gate_reason[arm] = "the anchor gate failed on %s" % arm
            else:
                out.append("anchor gate %s: passed (strong scores %s, all at least %d; "
                           "weak scores %s, all at most %d)"
                           % (arm, ", ".join(str(x.reply.score) for x in strong_recs),
                              plan.strong_at_least,
                              ", ".join(str(x.reply.score) for x in weak_recs),
                              plan.weak_at_most))
        if arm in gate_reason:
            out.append("lens %s: not counted (%s)" % (arm, gate_reason[arm]))
        else:
            counted.append(arm)
            out.append("lens %s: counted" % arm)
        for document in DOCUMENTS:
            recs = valid_in(arm, document)
            pairs = [(x.read.reader, x.reply.score) for x in recs]
            line = _scores_line("scores %s %s" % (arm, document), pairs)
            if line is not None:
                out.append(line)
            if document == VERSION:
                for reader in plan.readers:
                    line = _scores_line("scores %s reader %s version" % (arm, reader.name),
                                        [p for p in pairs if p[0] == reader.name])
                    if line is not None:
                        out.append(line)
        version_recs = valid_in(arm, VERSION)
        for field in FREE_TEXT_FIELDS:
            out.append("flagged %s version %s: %d of %d valid reads"
                       % (arm, field, len([x for x in version_recs
                                           if field in x.reply.flagged]),
                          len(version_recs)))
    out.append("counted lenses: %s" % (" ".join(counted) if counted else "none"))

    # rules
    for rule in plan.rules:
        where = "overall" if rule.lens is None else rule.lens
        label = "rule %s (%s)" % (rule.name, where)
        if rule.lens is None:
            recs = [x for arm in counted for x in valid_in(arm, VERSION)]
        else:
            recs = valid_in(rule.lens, VERSION) if rule.lens in counted else []
        out.append("%s: %s" % (label, "; ".join("%s if %s" % (kind, clause.text())
                                                for kind, clause in rule.clauses)))
        verdict = "INCONCLUSIVE"
        decided = False
        for kind, clause in rule.clauses:
            holds, count = _clause_holds(clause, recs)
            out.append("%s count: %s: %d of %d valid reads" % (label, clause.test(), count,
                                                                len(recs)))
            if holds and not decided:
                verdict = kind
                decided = True
        reasons = []
        if rule.lens is None:
            if not counted:
                verdict = "INCONCLUSIVE"
                reasons.append("no lens is counted")
        elif rule.lens not in counted:
            verdict = "INCONCLUSIVE"
            reasons.append(gate_reason[rule.lens])
        out.append("%s verdict: %s" % (label, verdict))
        for reason in reasons:
            out.append("%s reason: %s" % (label, reason))

    return harness.finish_result(folder, out, records, log, stopped)
