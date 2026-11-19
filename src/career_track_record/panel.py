"""Reader panel: blind lens reads of one version, gated by an anchored rubric.

The behaviour is stated in docs/specs/reader-panel.md (revision 4). In short: freeze a plan and
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
from career_track_record import stats

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
# The line a freeze file holds to say which revision of the spec froze it.
REVISION_LINE = "revision: 4"
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
# A lens that names criteria is scored on reply fields CRITERION-<name>, summed by the tool.
CRITERION = "CRITERION-"
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

_PROMPT_COUNT = "Write these nine fields, in this order"
_PROMPT_SCORE = "SCORE: a whole number, as digits only, on the scale LENS.txt gives\n"


def criteria_prompt(criteria):
    """The prompt for a lens that names criteria: the built-in prompt with the SCORE field
    replaced by one field per criterion, in the lens's order, and the count of fields to
    match. No scale is stated."""
    lines = "".join("CRITERION-%s: a whole number, as digits only, for the criterion %s, on "
                    "the scale LENS.txt gives\n" % (name, name) for name in criteria)
    count = _PROMPT_COUNT.replace("nine", str(8 + len(criteria)))
    return PROMPT.replace(_PROMPT_COUNT, count).replace(_PROMPT_SCORE, lines)


def prompt_of(criteria):
    """The prompt a lens with these criteria (a tuple, empty for none) is read with."""
    return criteria_prompt(criteria) if criteria else PROMPT


# ------------------------------------------------------------------ the plan model

class Lens(object):
    """A lens: a reader role, read from a plain-text prompt file. ``arm`` is l1, l2 and so
    on in plan order."""

    def __init__(self, name, path, arm, max=None, author_edited=None, criteria=()):
        self.name = name
        self.path = path
        self.arm = arm
        self.max = max
        self.author_edited = author_edited
        self.criteria = tuple(criteria)


class FakeRule(object):
    """One rule of the fake reader. ``lenses`` names the arms it applies to (l1, l2, ...)
    and ``documents`` the documents (strong, weak, version); None means every one.
    ``on_reads`` is a set of read numbers counted across the lens."""

    KINDS = ("score", "score-containing", "write", "omit")

    def __init__(self, kind, score=None, text=None, field=None, lenses=None,
                 documents=None, on_reads=None):
        if kind not in self.KINDS:
            raise ValueError("unknown rule kind %r" % (kind,))
        if field is not None and field not in LABELS and not (
                field.startswith(CRITERION) and len(field) > len(CRITERION)):
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
                 anchor_reads_per_reader=2, rules=(), spend_ceiling=None, amends=None,
                 read_timeout=DEFAULT_READ_TIMEOUT, sidedness="two", min_valid_reads=None,
                 replicate_of=None, written_by=None, notes=None, calibration_only=False,
                 calibration=None, extends=None):
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
        self.min_valid_reads = min_valid_reads
        self.replicate_of = replicate_of
        # Who wrote each anchor, as stored text, and each anchor's note, if it has one.
        self.written_by = dict(written_by or {})
        self.notes = dict(notes or {})
        self.calibration_only = calibration_only
        self.calibration = calibration
        self.extends = extends

    def criteria_forms(self):
        """The distinct criteria lists of the plan's lenses, in lens order."""
        found = []
        for lens in self.lenses:
            if lens.criteria and lens.criteria not in found:
                found.append(lens.criteria)
        return found

    def document_path(self, document):
        if document == VERSION:
            return self.version
        return self.anchors[document]

    def reads_per_document(self, document):
        if document == VERSION and self.calibration_only:
            return 0  # a calibration run plans no read of the version
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
                "replicate-of", "read-timeout", "sidedness", "min-valid-reads",
                "calibration-only", "calibration", "extends")
_NAME = harness.NAME
_CLAUSE = re.compile(r"(PASS|FAIL) if (?:score at (least|most) (-?[0-9]+)"
                     r"|([A-Z-]+|CRITERION-[A-Za-z0-9-]+) (flagged|not flagged)) in "
                     r"(?:([0-9]+) of ([0-9]+)|([0-9]+) or more)\Z")
_FAMILY = re.compile(r"[A-Za-z0-9-]+\Z")
_EXTRAS = ("a lens's extra fields may be max <n>, author-edited-version yes or no, and "
           "criteria <names>, each at most once: %s")
_QUOTED = harness.QUOTED
_short = harness.short


def parse(path):
    """Read a plan file and return a Plan. Raises PlanError, naming each problem with the
    plan line number where there is one."""
    return parse_text(harness.plan_text(path))


def parse_text(text):
    """The work of ``parse``, on the text of a plan. A whole number in a plan has any number
    of digits, so the whole parse runs with the digit limit lifted."""
    with harness.unlimited_int_digits():
        return _parse_text(text)


def _parse_text(text):
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
    anchor_reads = 2
    if "anchor-reads-per-reader" in scalars:
        number, value = scalars["anchor-reads-per-reader"]
        got = state.integer(number, "anchor-reads-per-reader", value, minimum=1)
        anchor_reads = got if got is not None else 2
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
    replicate_of = None
    if "replicate-of" in scalars:
        number, replicate_of = scalars["replicate-of"]
        if not replicate_of.endswith(harness.FREEZE_SUFFIX):
            state.bad(number, "replicate-of must name a .freeze file")
        if "amends" in scalars:
            state.bad(number, "a plan may not carry both replicate-of and amends")
    sidedness = "two"
    if "sidedness" in scalars:
        number, value = scalars["sidedness"]
        if value in ("two", "greater", "less"):
            sidedness = value
        else:
            state.bad(number, "sidedness is two, greater or less")

    min_valid_reads = None
    if "min-valid-reads" in scalars:
        number, value = scalars["min-valid-reads"]
        min_valid_reads = state.integer(number, "min-valid-reads", value, minimum=1)

    calibration = extends = None
    calibration_only = False
    if "calibration" in scalars:
        number, calibration = scalars["calibration"]
        if not calibration.endswith(harness.FREEZE_SUFFIX):
            state.bad(number, "calibration must name a .freeze file")
    if "extends" in scalars:
        number, extends = scalars["extends"]
        if not extends.endswith(harness.FREEZE_SUFFIX):
            state.bad(number, "extends must name a .freeze file")
        if "amends" in scalars or "replicate-of" in scalars:
            state.bad(number, "a plan may not carry extends with amends or replicate-of")
    if "calibration-only" in scalars:
        number, value = scalars["calibration-only"]
        if value == "yes":
            calibration_only = True
            if "rules" in lists:
                state.bad(lists["rules"][0][0] if lists["rules"] else number,
                          "a calibration-only plan reads no version, so it takes no rules")
            if "calibration" in scalars or "extends" in scalars or "replicate-of" in scalars:
                state.bad(number, "a calibration-only plan may not carry calibration, "
                          "extends or replicate-of")
        else:
            state.bad(number, "calibration-only is yes, or left out")

    # anchors
    anchors, written_by, notes = {}, {}, {}
    for number, item in lists.get("anchors", []):
        pieces = item.split(" | ")
        if any(not piece.strip() for piece in pieces[:3]):
            state.bad(number, "an empty field")
            continue
        parts = [piece.strip() for piece in pieces[:3]]
        if len(parts) < 2 or parts[0] not in ANCHORS:
            state.bad(number, "an anchor is written: strong | file, or weak | file")
            continue
        if parts[0] in anchors:
            state.bad(number, "the anchor %s is named twice" % parts[0])
            continue
        anchors[parts[0]] = parts[1]
        if len(parts) == 2:
            state.bad(number, "an anchor needs written-by (revision 4): %s" % parts[0])
            continue
        who = _written_by(parts[2])
        if who is None:
            state.bad(number, "written-by is user, third-party, unknown or model <family>, "
                      "with more models as a comma list: %s" % _short(parts[2]))
            continue
        written_by[parts[0]] = who
        if len(pieces) > 3:
            last = " | ".join(pieces[3:]).strip()
            if last == "note":
                state.bad(number, "a note needs text: %s" % parts[0])
            elif last.startswith("note "):
                notes[parts[0]] = last[len("note "):].strip()
            else:
                state.bad(number, "an anchor's last field may be note <text>: %s"
                          % _short(last))

    # lenses
    lenses, lens_names = [], []
    for number, item in lists.get("lenses", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) < 2:
            state.bad(number, "a lens is written: name | file")
            continue
        lens_max = None
        author_edited = None
        criteria = ()
        broken = False
        seen = set()
        for extra in parts[2:]:
            word = extra.split(" ", 1)[0]
            if word in ("max", "author-edited-version", "criteria") and word not in seen:
                seen.add(word)
                value = extra[len(word):].strip() if extra.startswith(word + " ") else None
                if word == "max":
                    if value is None or not re.fullmatch(r"-?[0-9]+", value):
                        state.bad(number, "a lens's max is a whole number: %s"
                                  % _short(value or ""))
                        broken = True
                        break
                    lens_max = int(value)
                    if strong_at_least is not None and lens_max < strong_at_least:
                        state.bad(number, "max %d is below anchor-strong-at-least (%d)"
                                  % (lens_max, strong_at_least))
                        broken = True
                        break
                elif word == "author-edited-version" and value in ("yes", "no"):
                    author_edited = value
                elif word == "criteria" and value is not None:
                    names = [name.strip() for name in value.split(",")]
                    if (all(_NAME.match(name) for name in names)
                            and len(set(names)) == len(names)):
                        criteria = tuple(names)
                    else:
                        state.bad(number, "criteria are names of letters, digits and -, "
                                  "separated by commas, each once: %s" % _short(value))
                else:
                    state.bad(number, _EXTRAS % _short(extra))
            else:
                state.bad(number, _EXTRAS % _short(extra))
        if broken:
            continue
        if not _NAME.match(parts[0]):
            state.bad(number, "a name holds letters, digits and - only: %s" % _short(parts[0]))
        elif parts[0] in RESERVED:
            state.bad(number, "a lens may not be named %s" % parts[0])
        elif parts[0] in lens_names:
            state.bad(number, "the lens %s is named twice" % parts[0])
        else:
            if author_edited is None and "author-edited-version" not in seen:
                state.bad(number, "a lens needs author-edited-version yes or no "
                          "(revision 4): %s" % parts[0])
            lens_names.append(parts[0])
            lenses.append(Lens(parts[0], parts[1], "l%d" % (len(lenses) + 1), max=lens_max,
                               author_edited=author_edited, criteria=criteria))
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
    criteria_of = dict((lens.arm, lens.criteria) for lens in lenses)
    fake_rules, rule_lines = [], []
    for number, item in lists.get("fake-reader", []):
        rule = _fake_rule(state, number, item, arms, reads, criteria_of)
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
                amends=amends, read_timeout=timeout, sidedness=sidedness,
                min_valid_reads=min_valid_reads, replicate_of=replicate_of,
                written_by=written_by, notes=notes, calibration_only=calibration_only,
                calibration=calibration, extends=extends)


def _written_by(text):
    """The stored form of a written-by field, or None when it is not one: ``user``,
    ``third-party``, ``unknown``, or one or more ``model <family>`` joined by a comma and a
    space, each family lower-cased and kept once."""
    if not text.startswith("written-by "):
        return None
    who = text[len("written-by "):].strip()
    if who in ("user", "third-party", "unknown"):
        return who
    families = []
    for piece in who.split(", "):
        if not piece.startswith("model ") or not _FAMILY.match(piece[len("model "):]):
            return None
        family = piece[len("model "):].lower()
        if family not in families:
            families.append(family)
    return ", ".join("model " + family for family in families)


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


def _fake_rule(state, number, item, arms, reads, criteria_of=None):
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
        with harness.unlimited_int_digits():
            return FakeRule.score_of(int(match.group(1)), **mods)
    match = re.match(r"score containing " + _QUOTED + r" (-?[0-9]+)\Z", rule_text)
    if match:
        with harness.unlimited_int_digits():
            return FakeRule.score_containing(match.group(1), int(match.group(2)), **mods)
    named = r"([A-Z-]+|CRITERION-[A-Za-z0-9-]+)\Z"

    def known(field):
        if field in LABELS:
            return True
        if not field.startswith(CRITERION) or lenses is None:
            return False
        return field[len(CRITERION):] in (criteria_of or {}).get(lenses[0], ())

    match = re.match(r"write " + _QUOTED + r" in " + named, rule_text)
    if match:
        if not known(match.group(2)):
            state.bad(number, "not a reply field: %s" % _short(match.group(2)))
            return None
        return FakeRule.write(match.group(2), match.group(1), **mods)
    match = re.match(r"omit " + named, rule_text)
    if match:
        if not known(match.group(1)):
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
    posting, the version, both anchors, every lens file and any amended, replicated,
    calibration or extended freeze."""
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
    if plan.replicate_of is not None:
        items.append((plan.replicate_of, os.path.join(folder, plan.replicate_of)))
    if plan.calibration is not None:
        items.append((plan.calibration, os.path.join(folder, plan.calibration)))
    if plan.extends is not None:
        items.append((plan.extends, os.path.join(folder, plan.extends)))
    return harness.unique_inputs(items)


def criteria_label(criteria):
    """The freeze-file label of the prompt form for a lens with these criteria."""
    return "%s, criteria %s)" % (PROMPT_LABEL[:-1], ",".join(criteria))


def prompt_forms(plan_path):
    """The (label, sha256) of each prompt form beyond the first that the plan's lenses use,
    in lens order. A plan that cannot be read has none: its problems are reported by the
    harness."""
    try:
        plan = parse(plan_path)
    except PlanError:
        return ()
    return tuple((criteria_label(criteria),
                  hashlib.sha256(prompt_of(criteria).encode("utf-8")).hexdigest())
                 for criteria in plan.criteria_forms())


# ------------------------------------------------------------------ calibration, amendments, extensions

AMEND_RULE = ("an amendment may restate a rule's counts at the same share, and change nothing "
              "else: ")
EXTEND_ONLY = ("an extension may change only reads-per-reader, anchor-reads-per-reader and the "
               "number of readers of each model: ")
# The plan keys an extension may write differently from its first plan.
SAMPLE_SIZE_KEYS = ("reads-per-reader", "anchor-reads-per-reader", "readers", "extends")
# The thresholds an amendment keeps: (plan key, Plan attribute).
THRESHOLDS = (("anchor-strong-at-least", "strong_at_least"),
              ("anchor-weak-at-most", "weak_at_most"))


def _read_plan(path):
    """The Plan in ``path``, or None when it cannot be read under revision 4."""
    try:
        return parse(path)
    except (PlanError, OSError, Unreadable, RunFolderError, UnicodeDecodeError):
        return None


def _freeze_entries(folder, named):
    """(freeze path, recorded hashes by label, or None) of the freeze file ``named``, relative
    to ``folder``."""
    freeze_path = os.path.join(folder, named)
    if not os.path.isfile(freeze_path):
        return freeze_path, None
    try:
        return freeze_path, dict(harness.read_freeze(freeze_path))
    except (OSError, UnicodeDecodeError):
        return freeze_path, None


def _named_plan(folder, text, missing, cannot):
    """(Plan or None, freeze path, recorded hashes, problems) of the earlier plan whose freeze
    file the plan names as ``text`` (in ``amends``, ``calibration`` or ``extends``). No problem
    and no plan when the freeze file is not there (the freeze reports it as a missing input).
    The plan must be there, be the one the freeze recorded, have been frozen under revision 4
    and read under revision 4."""
    freeze_path, recorded = _freeze_entries(folder, text)
    if not os.path.isfile(freeze_path):
        return None, freeze_path, None, []
    if recorded is None:
        return None, freeze_path, None, ["cannot read the freeze file: %s" % _show(text)]
    named = text[:-len(FREEZE_SUFFIX)]
    plan_file = freeze_path[:-len(FREEZE_SUFFIX)]
    if not os.path.isfile(plan_file):
        return None, freeze_path, recorded, ["%s: %s" % (missing, _show(named))]
    if recorded.get(os.path.basename(plan_file)) != harness.sha256_file(plan_file):
        return None, freeze_path, recorded, ["changed since the freeze: %s" % _show(named)]
    if _revision_problem(freeze_path) is not None:
        return None, freeze_path, recorded, ["frozen under an earlier revision: %s" % _show(text)]
    earlier = _read_plan(plan_file)
    if earlier is None:
        return None, freeze_path, recorded, ["%s: %s" % (cannot, _show(named))]
    return earlier, freeze_path, recorded, []


def _blind_reads(plan):
    """The version reads each lens plans for the plan's blind readers."""
    return len([r for r in plan.readers if not r.not_blind]) * plan.reads_per_reader


def _rule_reads(plan, rule):
    """The reads ``rule`` counts when every planned read of the version is valid: one lens's,
    or every lens's for an ``overall`` rule."""
    return _blind_reads(plan) * (len(plan.lenses) if rule.lens is None else 1)


def _lens_name(plan, rule):
    return None if rule.lens is None else plan.lens_of(rule.lens).name


def _scaled(count, old, new):
    """``count`` over ``old`` planned reads, restated over ``new``, as an exact fraction; None
    when there is no share to restate."""
    return Fraction(count * new, old) if old else None


def _is_whole(value):
    return value is not None and value.denominator == 1


def _same_shape(a, b):
    """Whether two rules agree in everything but their counts: the null share, and each
    clause's verdict word, test and form."""
    if a.null_share_text != b.null_share_text or len(a.clauses) != len(b.clauses):
        return False
    for (kind_a, clause_a), (kind_b, clause_b) in zip(a.clauses, b.clauses):
        if (kind_a, clause_a.kind, clause_a.threshold, clause_a.field,
                clause_a.n is None) != (kind_b, clause_b.kind, clause_b.threshold,
                                        clause_b.field, clause_b.n is None):
            return False
    return True


def _same_share(count_old, count_new, total_old, total_new):
    """Whether ``count_new`` over ``total_new`` is exactly ``count_old`` over ``total_old``."""
    if total_old == total_new:
        return count_old == count_new
    need = _scaled(count_old, total_old, total_new)
    return _is_whole(need) and need == count_new


def _calibration_problems(plan_path, plan):
    """The problems of the calibration the plan names, in order: it must be a calibration-only
    run of another folder, and each of this plan's lenses must be the file it recorded."""
    if plan.calibration is None or not plan.calibration.endswith(FREEZE_SUFFIX):
        return []
    folder = harness.folder_of(plan_path)
    freeze_path = os.path.join(folder, plan.calibration)
    if not os.path.isfile(freeze_path):
        return []
    if os.path.realpath(os.path.dirname(freeze_path)) == os.path.realpath(folder):
        return ["calibration names a run in this folder: %s" % _show(plan.calibration)]
    earlier, _path, recorded, problems = _named_plan(
        folder, plan.calibration, "the calibration plan is missing",
        "the calibration plan cannot be read under revision 4")
    if earlier is None:
        return problems
    named = plan.calibration[:-len(FREEZE_SUFFIX)]
    if not earlier.calibration_only:
        return ["calibration must name a calibration-only run: %s" % _show(named)]
    for lens in plan.lenses:
        theirs = [x for x in earlier.lenses if x.name == lens.name]
        if not theirs or theirs[0].path not in recorded:
            problems.append("the calibration recorded no hash for the lens: %s"
                            % _show(lens.name))
            continue
        path = os.path.join(folder, lens.path)
        if os.path.isfile(path) and harness.sha256_file(path) != recorded[theirs[0].path]:
            problems.append("the lens file differs from the calibration's: %s"
                            % _show(lens.name))
    return problems


def _amendment_problems(plan_path, plan):
    """The problems of an amendment against the plan it amends, in order. An amendment may
    change the read counts, never a threshold or a rule's bars: each count in a rule keeps its
    share of the reads the rule counts, as an exact fraction, and a share with no whole count
    is refused."""
    if plan.amends is None or not plan.amends.endswith(FREEZE_SUFFIX):
        return []
    old, _path, _recorded, problems = _named_plan(
        harness.folder_of(plan_path), plan.amends, "the amended plan is missing",
        "the amended plan cannot be read under revision 4")
    if old is None:
        return problems
    for key, attribute in THRESHOLDS:
        if getattr(old, attribute) != getattr(plan, attribute):
            problems.append("an amendment may not change %s from the plan it amends" % key)
    if old.calibration_only != plan.calibration_only:
        problems.append("an amendment keeps calibration-only as the plan it amends has it")
    for index in range(max(len(old.rules), len(plan.rules))):
        if index >= len(old.rules) or index >= len(plan.rules):
            longer = plan.rules if index < len(plan.rules) else old.rules
            problems.append(AMEND_RULE + longer[index].name)
            continue
        before, after = old.rules[index], plan.rules[index]
        ok = _lens_name(old, before) == _lens_name(plan, after) and _same_shape(before, after)
        if ok:
            reads_old, reads_new = _rule_reads(old, before), _rule_reads(plan, after)
            for (_k1, c1), (_k2, c2) in zip(before.clauses, after.clauses):
                ok = ok and _same_share(c1.k, c2.k, reads_old, reads_new)
                if c1.n is not None:
                    ok = ok and _same_share(c1.n, c2.n, reads_old, reads_new)
        if not ok:
            problems.append(AMEND_RULE + after.name)
    return problems


def pooled_rules(plan, first):
    """(the plan's rules with each count read at its share of the pooled planned reads, the
    problems): the first plan's reads and this plan's together are P and the first plan's are
    N, so each count ``k`` (and each ``m`` of ``k of m``) becomes k times P over N. A count
    with no whole result is a problem naming the rule, and keeps its written count."""
    problems, rules = [], []
    for rule in plan.rules:
        first_reads = _rule_reads(first, rule)
        pooled = first_reads + _rule_reads(plan, rule)
        clauses, whole = [], True
        for kind, clause in rule.clauses:
            k = _scaled(clause.k, first_reads, pooled)
            n = None if clause.n is None else _scaled(clause.n, first_reads, pooled)
            if not _is_whole(k) or (clause.n is not None and not _is_whole(n)):
                whole = False
                break
            clauses.append((kind, Clause(clause.kind, int(k), None if n is None else int(n),
                                         threshold=clause.threshold, field=clause.field)))
        if whole:
            rules.append(Rule(rule.name, rule.lens, clauses, null_share=rule.null_share,
                              null_share_text=rule.null_share_text))
        else:
            problems.append("an extension's pooled reads give no whole number for %s"
                            % rule.name)
            rules.append(rule)
    return rules, problems


def _models(plan):
    return [(r.command, r.not_blind, r.cost, r.group) for r in plan.readers]


def _structure_of(path):
    state = harness.ParseState()
    return harness.structure(state, harness.plan_text(path), _LIST_KEYS, _SCALAR_KEYS)


def _extension_problems(plan_path, plan):
    """The problems of an extension against its first run, in order. An extension may change
    the sample size only: the reads per reader and the number of readers of each model."""
    if plan.extends is None or not plan.extends.endswith(FREEZE_SUFFIX):
        return []
    folder = harness.folder_of(plan_path)
    first, freeze_path, recorded, problems = _named_plan(
        folder, plan.extends, "the first plan is missing",
        "the first plan cannot be read under revision 4")
    if first is None:
        return problems
    named = plan.extends[:-len(FREEZE_SUFFIX)]
    if (first.extends is not None or first.amends is not None
            or first.replicate_of is not None or first.calibration_only):
        return ["extends must name a first run, not an amendment, a replicate, an extension or "
                "a calibration: %s" % _show(named)]
    mine_scalars, mine_lists = _structure_of(plan_path)
    first_scalars, first_lists = _structure_of(freeze_path[:-len(FREEZE_SUFFIX)])
    for key in sorted(set(mine_scalars) | set(first_scalars) | set(mine_lists)
                      | set(first_lists)):
        if key in SAMPLE_SIZE_KEYS:
            continue
        mine = (mine_scalars[key][1] if key in mine_scalars
                else [x for _n, x in mine_lists.get(key, [])] if key in mine_lists else None)
        theirs = (first_scalars[key][1] if key in first_scalars
                  else [x for _n, x in first_lists.get(key, [])] if key in first_lists
                  else None)
        if mine != theirs:
            problems.append(EXTEND_ONLY + key)
    models = _models(plan)
    if set(models) != set(_models(first)):
        problems.append(EXTEND_ONLY + "readers")
    by_name = dict((r.name, m) for r, m in zip(first.readers, _models(first)))
    for reader, model in zip(plan.readers, models):
        if reader.name in by_name and by_name[reader.name] != model:
            if EXTEND_ONLY + "readers" not in problems:
                problems.append(EXTEND_ONLY + "readers")
    for index, (label, path) in enumerate(_inputs(plan, plan_path)):
        if index == 0 or label == plan.extends or not os.path.isfile(path):
            continue
        if recorded.get(label) != harness.sha256_file(path):
            problems.append("changed since the first freeze: %s" % _show(label))
    forms = [(PROMPT_LABEL, prompt_sha256())] + list(prompt_forms(plan_path))
    for label, digest in forms:
        if recorded.get(label) != digest:
            problems.append("changed since the first freeze: %s" % label)
    problems += pooled_rules(plan, first)[1]
    # one extension for each first run: look beside this run folder for another
    parent = os.path.dirname(folder)
    try:
        beside = sorted(os.listdir(parent))
    except OSError:
        beside = []
    for name in beside:
        other = os.path.join(parent, name)
        if os.path.realpath(other) == os.path.realpath(folder) or not os.path.isdir(other):
            continue
        try:
            files = [n for n in os.listdir(other) if n.endswith(FREEZE_SUFFIX)]
        except OSError:
            continue
        for file_name in sorted(files):
            their = _read_plan(os.path.join(other, file_name[:-len(FREEZE_SUFFIX)]))
            if (their is not None and their.extends is not None
                    and os.path.realpath(os.path.join(other, their.extends))
                    == os.path.realpath(freeze_path)):
                problems.append("the first run already has an extension: %s" % _show(name))
    return problems


def _freeze_problems(plan_path):
    """What the plan names that no revision 4 freeze can stand behind, found before the
    harness's own checks: a replicate's first freeze must record revision 4, a calibration
    must be a calibration-only run whose lens files the plan keeps, an amendment keeps every
    threshold and restates each count at its share, and an extension changes the sample size
    only."""
    try:
        plan = parse(plan_path)
    except PlanError:
        return []
    with harness.unlimited_int_digits():
        problems = []
        if plan.replicate_of is not None:
            named = os.path.join(harness.folder_of(plan_path), plan.replicate_of)
            if os.path.isfile(named) and _revision_problem(named) is not None:
                problems.append("frozen under an earlier revision: %s"
                                % _show(plan.replicate_of))
        problems += _calibration_problems(plan_path, plan)
        problems += _amendment_problems(plan_path, plan)
        problems += _extension_problems(plan_path, plan)
        return problems


def freeze(plan_path):
    """Read the plan, hash it and every input it names, and write the freeze file beside it.
    Every plan problem is found here."""
    problems = _freeze_problems(plan_path)
    if problems:
        return Result(2, False, error="\n".join(problems))
    return harness.freeze(plan_path, parse, _inputs, prompt_sha256(),
                          prompt_forms=prompt_forms(plan_path), record_lines=(REVISION_LINE,))


def _verify(plan_path, with_prompt):
    return harness.verify(plan_path, parse, _inputs, prompt_sha256(), with_prompt,
                          prompt_forms=prompt_forms(plan_path))


def _revision_problem(freeze_path):
    """None when the freeze file holds exactly one line ``revision: 4``, or when it is
    missing or cannot be read (the harness reports those), else the problem."""
    try:
        with open(freeze_path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
    except (OSError, UnicodeDecodeError):
        return None
    if lines.count(REVISION_LINE) == 1:
        return None
    return "frozen under an earlier revision"


def _earlier_revision(plan_path):
    """The one-line refusal for a plan whose freeze file is not a revision 4 one, or None."""
    freeze_path = plan_path + FREEZE_SUFFIX
    if _revision_problem(freeze_path) is None:
        return None
    return Result(2, False, error=(
        "frozen under an earlier revision: %s; score it with the release that froze it, or "
        "rewrite it as a new plan" % _show(os.path.basename(freeze_path))))


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


def reply_labels(criteria=()):
    """The field names of a reply: the fixed ones, and a CRITERION-<name> for each criterion
    of the lens, after SCORE."""
    labels = LABELS[:3] + tuple(CRITERION + name for name in criteria) + LABELS[3:]
    return labels


def parse_reply(text, criteria=()):
    """Parse a reply. A field starts a line as ``FIELD: value`` (case-sensitive) and runs to
    the next line that starts with a field name; text before the first field is ignored.
    For a lens with ``criteria`` the read's score is the sum of its criterion fields: a
    missing one, a repeated one or one that is not an integer fails the read, and a SCORE
    field is parsed so that it never runs into another field, but never read as a score."""
    reply = Reply()
    fields, _first, repeated = harness.split_fields(text, reply_labels(criteria))
    reply.fields = fields
    reply.prior_flag = harness.prior_flag(fields)
    reply.flagged = tuple(f for f in FREE_TEXT_FIELDS if fields.get(f, "") not in ("", NONE))
    if repeated:
        reply.failure = "%s appears twice" % repeated[0]
        return reply
    required = ("READ",) + (tuple(CRITERION + name for name in criteria) if criteria
                            else ("SCORE",))
    for label in required:
        if label not in fields:
            reply.failure = "missing %s" % label
            return reply
    reply.read_id = fields["READ"]
    if not criteria:
        with harness.unlimited_int_digits():
            reply.score = harness.whole_number(fields["SCORE"])
        if reply.score is None:
            reply.failure = "SCORE is not an integer"
        return reply
    total = 0
    with harness.unlimited_int_digits():
        for name in criteria:
            value = harness.whole_number(fields[CRITERION + name])
            if value is None:
                reply.failure = "%s%s is not an integer" % (CRITERION, name)
                return reply
            total += value
    reply.score = total
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
        for document in (ANCHORS if plan.calibration_only else DOCUMENTS):
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


def fake_reply(read, rules, text, criteria=()):
    """The text of the fake reader's reply to one read of the document ``text``. For a lens
    with ``criteria`` the reply carries SCORE as for any lens, then each CRITERION field that
    a write rule wrote, in the lens's criteria order; one no rule wrote is absent."""
    score = 5
    for rule in rules:
        if not _fires(rule, read):
            continue
        if rule.kind == "score":
            score = rule.score
        elif rule.kind == "score-containing" and rule.text in text:
            score = rule.score
    with harness.unlimited_int_digits():
        score_text = str(score)
    values = {"READ": read.id, "PRIOR": "nothing", "SCORE": score_text}
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
    return "".join("%s: %s\n" % (label, values[label]) for label in reply_labels(criteria)
                   if label not in omitted and label in values)


# ------------------------------------------------------------------ run

def run(plan_path, live=False):
    """Check, key, read and score. Writes the key, the reads, the run log and a result."""
    try:
        return _run(plan_path, live)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def _first_folder(plan_path, plan):
    """The folder of the first run, as the plan's replicate-of text names it, or None."""
    if plan.replicate_of is None:
        return None
    return os.path.dirname(os.path.join(harness.folder_of(plan_path), plan.replicate_of))


def _first_run_problems(plan_path, plan):
    """A replicate and an extension wait for their first run, and a plan that names a
    calibration waits for it: each such folder must already hold a key, and the plan an
    extension or a calibration names must still be the one its freeze recorded. Nothing in
    those folders is written."""
    folder = harness.folder_of(plan_path)
    problems = []
    first = _first_folder(plan_path, plan)
    if first is not None and not os.path.isfile(os.path.join(first, KEY_FILE)):
        problems.append("the first run has not been run yet: %s"
                        % _show(os.path.dirname(plan.replicate_of)))
    if plan.extends is not None:
        if not os.path.isfile(os.path.join(os.path.dirname(os.path.join(folder, plan.extends)),
                                           KEY_FILE)):
            problems.append("the first run has not been run yet: %s"
                            % _show(os.path.dirname(plan.extends)))
        else:
            problems += _named_plan(folder, plan.extends, "the first plan is missing",
                                    "the first plan cannot be read under revision 4")[3]
    if plan.calibration is not None:
        if not os.path.isfile(os.path.join(os.path.dirname(os.path.join(folder,
                                                                        plan.calibration)),
                                           KEY_FILE)):
            problems.append("the calibration run has not been run yet: %s"
                            % _show(os.path.dirname(plan.calibration)))
        else:
            problems += _named_plan(folder, plan.calibration,
                                    "the calibration plan is missing",
                                    "the calibration plan cannot be read under revision 4")[3]
    return problems


def _run(plan_path, live):
    folder = harness.folder_of(plan_path)
    earlier = _earlier_revision(plan_path)
    if earlier is not None:
        return earlier
    plan, problems, recorded, freeze_hash = _verify(plan_path, with_prompt=True)
    if plan is not None:
        problems += _document_problems(plan, plan_path)
    problems += harness.run_folder_problems(folder)
    if plan is not None:
        problems += _first_run_problems(plan_path, plan)
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
        harness.write_new(folder, os.path.join(where, READ_PROMPT),
                          prompt_of(plan.lens_of(read.arm).criteria))

    def reply_of(read):
        criteria = plan.lens_of(read.arm).criteria
        if criteria:
            return fake_reply(read, plan.fake_rules, texts[read.document], criteria=criteria)
        return fake_reply(read, plan.fake_rules, texts[read.document])

    stopped = harness.run_reads(folder, planned, plan.readers, plan.spend_ceiling,
                                plan.read_timeout, key_text, prepare, reply_of)
    return harness.scored_after_run(
        stopped, lambda: _score_and_write(plan_path, plan, recorded, freeze_hash))


def score(plan_path):
    """Score the replies in the run folder again, against the frozen plan. Writes a new result."""
    def write(plan, recorded, freeze_hash):
        problems = _first_run_problems(plan_path, plan)
        if problems:
            return Result(2, False, error="\n".join(problems))
        return _score_and_write(plan_path, plan, recorded, freeze_hash)

    earlier = _earlier_revision(plan_path)
    if earlier is not None:
        return earlier
    return harness.score(plan_path, parse, _inputs, prompt_sha256(), 3, write,
                         prompt_forms=prompt_forms(plan_path))


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


def _gate_state(plan, strong_recs, weak_recs, planned):
    """The anchor gate of one lens from its valid anchor reads and the number planned:
    "not evaluated", "failed" or "passed"."""
    if planned == 0 or len(strong_recs) + len(weak_recs) < planned:
        return "not evaluated"
    if (any(x.reply.score < plan.strong_at_least for x in strong_recs)
            or any(x.reply.score > plan.weak_at_most for x in weak_recs)):
        return "failed"
    return "passed"


def _first_counted_arms(plan, first_blind, first_reads, not_blind):
    """The lenses the first run counted: those whose anchor gate passed over the first
    run's own blind anchor reads."""
    counted = []
    for lens in plan.lenses:
        def valid(document):
            return [x for x in first_blind if x.read.arm == lens.arm
                    and x.read.document == document and x.status == "valid"]

        planned = len([r for r in first_reads if r.arm == lens.arm and r.document in ANCHORS
                       and r.reader not in not_blind])
        if _gate_state(plan, valid(STRONG), valid(WEAK), planned) == "passed":
            counted.append(lens.arm)
    return counted


def _replicate_lines(label, clauses, recs, first_recs):
    """The replicate lines of one rule: for each clause, its counted reads in the first
    run and in this one, with a two-sided Fisher exact p."""
    out = []
    for clause in clauses:
        k1 = len([x for x in first_recs if clause.holds_for(x.reply)])
        k2 = len([x for x in recs if clause.holds_for(x.reply)])
        n1, n2 = len(first_recs), len(recs)
        out.append("%s replicate: %s: first run %d of %d, this run %d of %d; "
                   "Fisher exact p = %s two-sided"
                   % (label, clause.test(), k1, n1, k2, n2,
                      stats.p_text(stats.fisher_p(k1, n1, k2, n2))))
    return out


SIDE_TEXT = {"two": "two-sided", "greater": "one-sided greater", "less": "one-sided less"}


def _evidence_line(label, clause, rule, recs, sidedness):
    """The evidence line of one clause: its count, its interval, and its p against a share."""
    n = len(recs)
    k = len([x for x in recs if clause.holds_for(x.reply)])
    head = "%s evidence: %s: %d of %d counted reads; " % (label, clause.test(), k, n)
    if n == 0:
        return head + "interval not computed"
    low, high = stats.wilson(k, n)
    if rule.null_share is None:
        return head + "95%% interval %s to %s" % (low, high)
    p = stats.p_text(stats.binomial_p(k, n, sidedness, rule.null_share))
    return head + ("p = %s %s against %s (reads may be correlated; may be too small); "
                   "95%% interval %s to %s" % (p, SIDE_TEXT[sidedness], rule.null_share_text,
                                               low, high))


def _possible_verdicts(rule, recs, m):
    """The verdicts ``rule`` could reach if ``m`` more version reads came in, each scoring
    anything and flagging any fields; one read decides all of the score clauses at once.
    Returns them in the order PASS, FAIL, INCONCLUSIVE."""
    return _completions(rule, recs, m)[0]


def _completions(rule, recs, m):
    """(the possible verdicts, whether a PASS among them is reached by a ``score at least``
    clause) of ``rule`` over ``recs`` and ``m`` more reads."""
    clauses = [clause for _kind, clause in rule.clauses]
    thresholds = [c.threshold for c in clauses if c.kind in ("at least", "at most")]
    scores = sorted(set(t + d for t in thresholds for d in (-1, 0, 1))) if thresholds else [0]
    fields = sorted(set(c.field for c in clauses if c.kind in ("flagged", "not flagged")))
    flag_sets = [[]]
    for field in fields:
        flag_sets = flag_sets + [s + [field] for s in flag_sets]
    vectors = set()
    for score in scores:
        for flags in flag_sets:
            vector = []
            for c in clauses:
                if c.kind == "at least":
                    vector.append(1 if score >= c.threshold else 0)
                elif c.kind == "at most":
                    vector.append(1 if score <= c.threshold else 0)
                elif c.kind == "flagged":
                    vector.append(1 if c.field in flags else 0)
                else:
                    vector.append(0 if c.field in flags else 1)
            vectors.add(tuple(vector))
    totals = set([tuple(0 for _c in clauses)])
    for _i in range(m):
        totals = set(tuple(a + b for a, b in zip(total, vector))
                     for total in totals for vector in vectors)
    base = [len([x for x in recs if c.holds_for(x.reply)]) for c in clauses]
    n = len(recs) + m
    found = set()
    by_score = False
    for total in totals:
        verdict = "INCONCLUSIVE"
        for (kind, clause), have, extra in zip(rule.clauses, base, total):
            count = have + extra
            holds = count >= clause.k if clause.n is None else (n == clause.n
                                                               and count >= clause.k)
            if holds:
                verdict = kind
                if kind == "PASS" and clause.kind == "at least":
                    by_score = True
                break
        found.add(verdict)
    return [v for v in ("PASS", "FAIL", "INCONCLUSIVE") if v in found], by_score


# ------------------------------------------------------------------ headroom

# The fewest valid reads of the strong anchor on a lens that headroom can be assessed from.
MIN_STRONG_READS = 3


def doubled_median(scores):
    """Twice the median of a non-empty list of whole numbers: exact, so that a median that is
    not whole is compared as a whole number."""
    ordered = sorted(scores)
    half = len(ordered) // 2
    if len(ordered) % 2:
        return 2 * ordered[half]
    return ordered[half - 1] + ordered[half]


def median_text(doubled):
    """A median, given doubled, as a whole number or with .5."""
    if doubled % 2 == 0:
        return str(doubled // 2)
    return "%s%d.5" % ("-" if doubled < 0 else "", abs(doubled) // 2)


class Headroom(object):
    """What a counted lens's headroom is: ``room`` (the strong anchor's median is above the
    version's), ``none``, ``few`` (too few valid strong-anchor reads) or ``no-version`` (no
    valid read of the version). ``strong`` and ``version`` hold the doubled medians where
    they were found."""

    ROOM, NONE, FEW, NO_VERSION = "room", "none", "few", "no-version"

    def __init__(self, state, valid, strong=None, version=None):
        self.state = state
        self.valid = valid
        self.strong = strong
        self.version = version

    def lines(self, arm):
        if self.state == self.FEW:
            return ["headroom %s: not assessed (%d valid strong-anchor reads, at least %d "
                    "needed)" % (arm, self.valid, MIN_STRONG_READS)]
        if self.state == self.NO_VERSION:
            return ["headroom %s: not assessed (no valid version read)" % arm]
        out = ["headroom %s: strong anchor median %s, version median %s"
               % (arm, median_text(self.strong), median_text(self.version))]
        if self.state == self.NONE:
            out.append("headroom %s: none; next step: a criterion rubric" % arm)
        return out

    def reason(self):
        """The reason a rule on this lens is not a PASS, or None when there is room."""
        if self.state == self.NONE:
            return "no headroom (strong anchor median %s, version median %s)" % (
                median_text(self.strong), median_text(self.version))
        if self.state == self.FEW:
            return ("headroom not assessed (%d valid strong-anchor reads, at least %d needed)"
                    % (self.valid, MIN_STRONG_READS))
        if self.state == self.NO_VERSION:
            return "headroom not assessed (no valid version read)"
        return None


def headroom_of(strong_scores, version_scores):
    """The Headroom of a counted lens from the scores of its valid, blind reads of the strong
    anchor and of the version."""
    if len(strong_scores) < MIN_STRONG_READS:
        return Headroom(Headroom.FEW, len(strong_scores))
    if not version_scores:
        return Headroom(Headroom.NO_VERSION, len(strong_scores))
    strong, version = doubled_median(strong_scores), doubled_median(version_scores)
    state = Headroom.ROOM if strong > version else Headroom.NONE
    return Headroom(state, len(strong_scores), strong, version)


# ------------------------------------------------------------------ a rule's verdict

class LensState(object):
    """What a rule needs of one lens: whether it is counted, why not, its valid blind reads
    of the strong anchor and of the version (records with a ``reply``), the version reads
    missing, and its Headroom when counted."""

    def __init__(self, arm, counted, gate_reason, strong, version, missing, headroom):
        self.arm = arm
        self.counted = counted
        self.gate_reason = gate_reason
        self.strong = strong
        self.version = version
        self.missing = missing
        self.headroom = headroom


class Outcome(object):
    """A rule's verdict: ``counts`` is (clause, reads that hold it) per clause, ``recs`` the
    reads it counted, ``m`` the missing reads, ``possible`` their completions or None."""

    def __init__(self, verdict, reasons, recs, counts, m, possible):
        self.verdict = verdict
        self.reasons = reasons
        self.recs = recs
        self.counts = counts
        self.m = m
        self.possible = possible


def _headroom_reason(rule, states, arms):
    """The reason headroom stops a PASS of ``rule`` on ``arms``, or None."""
    if rule.lens is not None:
        return states[rule.lens].headroom.reason()
    none = [a for a in arms if states[a].headroom.state == Headroom.NONE]
    unassessed = [a for a in arms if states[a].headroom.state in (Headroom.FEW,
                                                                  Headroom.NO_VERSION)]
    parts = []
    if none:
        parts.append("no headroom on %s" % ", ".join(none))
    if unassessed:
        parts.append("headroom not assessed on %s" % ", ".join(unassessed))
    return "; ".join(parts) if parts else None


def judge(plan, rule, states, counted):
    """The verdict of ``rule`` from the plan, the states of its lenses and the arms counted:
    the clauses, the counted lens, the read floor, the lift, then headroom."""
    arms = list(counted) if rule.lens is None else ([rule.lens] if rule.lens in counted
                                                     else [])
    recs = [x for arm in arms for x in states[arm].version]
    verdict, decided, counts = "INCONCLUSIVE", None, []
    for kind, clause in rule.clauses:
        holds, count = _clause_holds(clause, recs)
        counts.append((clause, count))
        if holds and decided is None:
            verdict, decided = kind, (kind, clause)
    reasons = []
    if rule.lens is None:
        if not counted:
            verdict = "INCONCLUSIVE"
            reasons.append("no lens is counted")
    elif rule.lens not in counted:
        verdict = "INCONCLUSIVE"
        reasons.append(states[rule.lens].gate_reason)
    floor = plan.min_valid_reads
    below = floor is not None and len(recs) < floor
    if below:
        verdict = "INCONCLUSIVE"
        reasons.append("below the read floor (%d counted reads, floor %d)" % (len(recs), floor))
    m = sum(states[arm].missing for arm in arms)
    possible, pass_by_score = _completions(rule, recs, m) if m >= 1 else (None, False)
    # a lift: settled under every completion, and nothing but the clauses made it INCONCLUSIVE
    lifted = False
    if (floor is not None and not below and not reasons and verdict == "INCONCLUSIVE"
            and possible is not None and len(possible) == 1
            and possible[0] in ("PASS", "FAIL")):
        verdict = possible[0]
        lifted = True
        reasons.append("lifted from INCONCLUSIVE: settled under every completion of %d "
                       "missing reads; read floor %d met" % (m, floor))
    # headroom, after the lift: it touches a PASS reached through a `score at least` clause
    if verdict == "PASS":
        score_pass = (pass_by_score if lifted else
                      decided is not None and decided[1].kind == "at least")
        if score_pass:
            reason = _headroom_reason(rule, states, arms)
            if reason is not None:
                verdict, reasons = "INCONCLUSIVE", [reason]
    return Outcome(verdict, reasons, recs, counts, m, possible)


def _score_and_write(plan_path, plan, recorded, freeze_hash):
    with harness.unlimited_int_digits():
        return _score_and_write_unlimited(plan_path, plan, recorded, freeze_hash)


def _load_records(folder, plan, log):
    """(planned reads, one record per read) of a run folder, each read parsed as its lens's
    reply form."""
    reads = [PlannedRead(*row) for row in harness.load_key(folder, 3)]
    unrun = log.get("cut") == "yes" or log.get("stopped") is not None
    failures = harness.log_failures(log)
    by_id = {}
    for criteria in set([()] + [lens.criteria for lens in plan.lenses]):
        mine = [r for r in reads if (plan.lens_of(r.arm).criteria
                                     if plan.lens_of(r.arm) else ()) == criteria]
        for record in harness.records(folder, mine, unrun, failures,
                                      lambda text, c=criteria: parse_reply(text, c)):
            by_id[record.read.id] = record
    return reads, [by_id[r.id] for r in reads]


class OtherRun(object):
    """What a run reads of another run folder, the first run of an extension or a
    calibration run: its plan, its reads and its records. Nothing there is written."""

    def __init__(self, plan_path, plan):
        self.plan_path = plan_path
        self.plan = plan
        self.folder = harness.folder_of(plan_path)
        self.log = harness.load_log(self.folder)
        self.reads, self.records = _load_records(self.folder, plan, self.log)
        self.not_blind = set(r.name for r in plan.readers if r.not_blind)


def _other_run(plan_path, text):
    """The OtherRun whose freeze file the plan names as ``text``."""
    path = os.path.join(harness.folder_of(plan_path), text)[:-len(FREEZE_SUFFIX)]
    return OtherRun(path, parse(path))


def _valid(records, not_blind, arm, document, only=None):
    """The valid records of one lens's reads of one document: blind readers' unless ``only``
    names the readers wanted."""
    return [x for x in records if x.read.arm == arm and x.read.document == document
            and x.status == "valid"
            and (x.read.reader not in not_blind if only is None else x.read.reader in only)]


def _planned(reads, not_blind, arm, document):
    return [r for r in reads if r.arm == arm and r.document == document
            and r.reader not in not_blind]


# ------------------------------------------------------------------ calibration

class Calibration(object):
    """A lens's calibration, from the valid blind reads of each anchor in a calibration run:
    passed when the median of the strong anchor's reads is at or above the strong threshold
    and the median of the weak anchor's reads is at or below the weak threshold. ``strong``
    and ``weak`` hold the doubled medians, None when an anchor has no valid read, which fails
    the calibration."""

    def __init__(self, plan, strong_scores, weak_scores):
        self.strong = doubled_median(strong_scores) if strong_scores else None
        self.weak = doubled_median(weak_scores) if weak_scores else None
        self.passed = (self.strong is not None and self.weak is not None
                       and self.strong >= 2 * plan.strong_at_least
                       and self.weak <= 2 * plan.weak_at_most)

    def line(self, arm):
        def shown(doubled):
            return "not assessable" if doubled is None else median_text(doubled)
        return "calibration %s: %s (strong median %s, weak median %s)" % (
            arm, "passed" if self.passed else "failed", shown(self.strong), shown(self.weak))


def _calibration_of(plan, records, not_blind, arm):
    """The Calibration of the lens ``arm`` of the calibration run's ``plan``."""
    return Calibration(
        plan, [x.reply.score for x in _valid(records, not_blind, arm, STRONG)],
        [x.reply.score for x in _valid(records, not_blind, arm, WEAK)])


def _calibration_failures(plan_path, plan):
    """The arms of the plan's lenses that failed the calibration the plan names, each lens
    matched to the calibration's lens of its name by name and judged by the calibration run's
    own replies. A lens the calibration holds no lens of that name for has failed."""
    if plan.calibration is None:
        return set()
    cal = _other_run(plan_path, plan.calibration)
    failed = set()
    for lens in plan.lenses:
        theirs = [x for x in cal.plan.lenses if x.name == lens.name]
        if not theirs or not _calibration_of(cal.plan, cal.records, cal.not_blind,
                                              theirs[0].arm).passed:
            failed.add(lens.arm)
    return failed


# ------------------------------------------------------------------ what the reads add up to

class Gate(object):
    """A lens's anchor gate over the reads it was given: ``state`` is "not evaluated",
    "failed" or "passed", ``strong`` and ``weak`` its valid anchor reads, ``planned`` the
    anchor reads it planned."""

    def __init__(self, state, strong, weak, planned):
        self.state = state
        self.strong = strong
        self.weak = weak
        self.planned = planned


class Standing(object):
    """Where each lens stands on the reads it was given: its ``gates`` and ``headrooms`` by
    arm, the ``counted`` arms, why the others are not (``gate_reason``) and the ``states`` a
    rule's verdict needs. Pure: it reads the plan, the planned reads and the records, never
    the run folder, so it can be asked of one run alone or of pooled reads."""

    def __init__(self):
        self.gates = {}
        self.headrooms = {}
        self.counted = []
        self.gate_reason = {}
        self.states = {}


def _standing(plan, reads, records, not_blind, failed_calibration=()):
    """The Standing of the plan's lenses on ``reads`` and ``records``, leaving out the readers
    ``not_blind`` names; a lens in ``failed_calibration`` is not counted."""
    standing = Standing()
    for lens in plan.lenses:
        arm = lens.arm
        strong = _valid(records, not_blind, arm, STRONG)
        weak = _valid(records, not_blind, arm, WEAK)
        planned = (len(_planned(reads, not_blind, arm, STRONG))
                   + len(_planned(reads, not_blind, arm, WEAK)))
        gate = Gate(_gate_state(plan, strong, weak, planned), strong, weak, planned)
        standing.gates[arm] = gate
        if arm in failed_calibration:
            standing.gate_reason[arm] = "%s failed its calibration" % arm
        elif gate.state == "not evaluated":
            standing.gate_reason[arm] = "the anchor gate was not evaluated on %s" % arm
        elif gate.state == "failed":
            standing.gate_reason[arm] = "the anchor gate failed on %s" % arm
        else:
            standing.counted.append(arm)
        version = _valid(records, not_blind, arm, VERSION)
        if arm in standing.counted and not plan.calibration_only:
            standing.headrooms[arm] = headroom_of([x.reply.score for x in strong],
                                                  [x.reply.score for x in version])
    for lens in plan.lenses:
        arm = lens.arm
        missing = [x for x in records if x.read.arm == arm and x.read.document == VERSION
                   and x.read.reader not in not_blind and x.status != "valid"]
        standing.states[arm] = LensState(
            arm, arm in standing.counted, standing.gate_reason.get(arm),
            standing.gates[arm].strong, _valid(records, not_blind, arm, VERSION),
            len(missing), standing.headrooms.get(arm))
    return standing


def _score_and_write_unlimited(plan_path, plan, recorded, freeze_hash):
    folder = harness.folder_of(plan_path)
    log = harness.load_log(folder)
    stopped = log.get("stopped")
    reads, records = _load_records(folder, plan, log)
    # I-1 and D:130: from revision 3, reads from a not-blind reader are left out of every
    # rule, anchor gate, score, flag count and missing-read count; _valid and _planned
    # return blind readers' reads unless a caller names the readers it wants.
    not_blind = set(r.name for r in plan.readers if r.not_blind)
    first_blind = None
    first_counted = None
    if plan.replicate_of is not None:
        # The first run's folder is read, never written.
        first_folder = _first_folder(plan_path, plan)
        first_log = harness.load_log(first_folder)
        first_reads, first_records = _load_records(first_folder, plan, first_log)
        first_blind = [x for x in first_records if x.read.reader not in not_blind]
        first_counted = _first_counted_arms(plan, first_blind, first_reads, not_blind)
    # An extension reads its first run's reads pooled with its own, each rule's counts at their
    # share of the pooled planned reads; it also gives the first run's own verdict of each rule.
    # A lens that failed a named calibration is not counted, in either.
    ext = _other_run(plan_path, plan.extends) if plan.extends is not None else None
    failed_calibration = _calibration_failures(plan_path, plan)
    rules = plan.rules
    first_verdicts = None
    pool_reads, pool_records, pool_not_blind = reads, records, not_blind
    if ext is not None:
        rules = pooled_rules(plan, ext.plan)[0]
        pool_reads, pool_records = ext.reads + reads, ext.records + records
        pool_not_blind = ext.not_blind | not_blind
        first = _standing(ext.plan, ext.reads, ext.records, ext.not_blind,
                          _calibration_failures(ext.plan_path, ext.plan))
        first_verdicts = [judge(ext.plan, rule, first.states, first.counted).verdict
                          for rule in ext.plan.rules]
    standing = _standing(plan, pool_reads, pool_records, pool_not_blind, failed_calibration)
    # A run that reads the version and names no calibration reports its scores as uncalibrated.
    uncalibrated = not plan.calibration_only and plan.calibration is None
    out = []

    out.append("plan sha256: %s" % _show(recorded.get(os.path.basename(plan_path), "unknown")))
    out.append("freeze sha256: %s" % freeze_hash)
    if plan.amends is not None:
        out.append("amended freeze sha256: %s" % _show(recorded.get(plan.amends, "unknown")))
    out.append("prompt sha256: %s" % _show(recorded.get(PROMPT_LABEL, "unknown")))
    for criteria in plan.criteria_forms():
        out.append("prompt sha256 (criteria %s): %s" % (
            ",".join(criteria), _show(recorded.get(criteria_label(criteria), "unknown"))))
    if plan.replicate_of is not None:
        out.append("replicate of: %s" % _show(recorded.get(plan.replicate_of, "unknown")))
    if ext is not None:
        out.append("extends: %s; the sample size changed after a result was seen"
                   % _show(recorded.get(plan.extends, "unknown")))
    if uncalibrated:
        out.append("calibration: none; scores are uncalibrated")
    elif plan.calibration is not None:
        out.append("calibration: %s" % _show(recorded.get(plan.calibration, "unknown")))
    out.append("version: %s" % _show(plan.version))
    for anchor in ANCHORS:
        out.append("anchor %s: %s" % (anchor, _show(plan.anchors[anchor])))
    for anchor in ANCHORS:
        line = "anchor %s: written by %s" % (anchor, _show(plan.written_by[anchor]))
        if anchor in plan.notes:
            line += "; note: %s" % _show(plan.notes[anchor])
        out.append(line)
    out.append("anchor thresholds: strong at least %d; weak at most %d"
               % (plan.strong_at_least, plan.weak_at_most))
    for lens in plan.lenses:
        out.append("lens %s: %s (%s, sha256 %s)" % (lens.arm, _show(lens.name),
                                                     _show(lens.path),
                                                     _show(recorded.get(lens.path, "unknown"))))
        out.append("%s author edited the version: %s" % (lens.arm, lens.author_edited))
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
        return _valid(records, not_blind, arm, document, only)

    def planned_in(arm, document):
        return _planned(reads, not_blind, arm, document)

    # each lens: its reads, its anchor gate, whether it is counted, its scores and flags. The
    # gate, the counted lens and the headroom read the pooled reads of an extension; the reads,
    # scores and flags shown are this run's.
    documents = ANCHORS if plan.calibration_only else DOCUMENTS
    counted = standing.counted
    for lens in plan.lenses:
        arm = lens.arm
        who = "blind readers" if not_blind else "all readers"
        for document in ANCHORS:
            if not_blind:
                out.append("reads blind readers %s %s: valid=%d of %d planned"
                           % (arm, document, len(valid_in(arm, document)),
                              len(planned_in(arm, document))))
            else:
                out.append("reads %s %s: valid=%d of %d planned"
                           % (arm, document, len(valid_in(arm, document)),
                              len(planned_in(arm, document))))
        if not plan.calibration_only:
            out.append("reads %s %s version: valid=%d of %d planned"
                       % (who, arm, len(valid_in(arm, VERSION)), len(planned_in(arm, VERSION))))
            out.append("reads not-blind readers %s version: valid=%d"
                       % (arm, len(valid_in(arm, VERSION, not_blind))))
        gate = standing.gates[arm]
        strong_recs, weak_recs = gate.strong, gate.weak
        if gate.state == "not evaluated":
            out.append("anchor gate %s: not evaluated (%d valid anchor reads of %d planned)"
                       % (arm, len(strong_recs) + len(weak_recs), gate.planned))
        else:
            low = ["%s read %s scored %d, below %d" % (STRONG, _show(x.read.id),
                                                       x.reply.score, plan.strong_at_least)
                   for x in strong_recs if x.reply.score < plan.strong_at_least]
            high = ["%s read %s scored %d, above %d" % (WEAK, _show(x.read.id),
                                                        x.reply.score, plan.weak_at_most)
                    for x in weak_recs if x.reply.score > plan.weak_at_most]
            if gate.state == "failed":
                out.append("anchor gate %s: failed (%s)" % (arm, "; ".join(low + high)))
            else:
                out.append("anchor gate %s: passed (strong scores %s, all at least %d; "
                           "weak scores %s, all at most %d)"
                           % (arm, ", ".join(str(x.reply.score) for x in strong_recs),
                              plan.strong_at_least,
                              ", ".join(str(x.reply.score) for x in weak_recs),
                              plan.weak_at_most))
        if arm in standing.gate_reason:
            out.append("lens %s: not counted (%s)" % (arm, standing.gate_reason[arm]))
        else:
            out.append("lens %s: counted" % arm)
        for document in documents:
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
        if not plan.calibration_only:
            for field in FREE_TEXT_FIELDS:
                out.append("flagged %s version %s: %d of %d valid reads"
                           % (arm, field, len([x for x in version_recs
                                               if field in x.reply.flagged]),
                              len(version_recs)))
        # the top of the scale: the version against the strong anchor, its spread, the room above
        version_scores = [x.reply.score for x in version_recs]
        strong_scores = [x.reply.score for x in valid_in(arm, STRONG)]
        low_version = min(version_scores) if version_scores else None
        high_strong = max(strong_scores) if strong_scores else None
        spread = max(version_scores) - low_version if version_scores else None
        if not plan.calibration_only:
            if version_scores and strong_scores:
                out.append("scores %s version against strong anchor: lowest version score %d, "
                           "highest strong-anchor score %d" % (arm, low_version, high_strong))
            else:
                out.append("scores %s version against strong anchor: not assessable" % arm)
            if version_scores:
                out.append("scores %s version spread: %d (highest %d, lowest %d)"
                           % (arm, spread, max(version_scores), low_version))
            else:
                out.append("scores %s version spread: not assessable" % arm)
            if version_scores and strong_scores and low_version >= high_strong:
                out.append("scores %s: the version scores at or above the strong anchor; "
                           "this lens cannot rank it higher" % arm)
            if len(version_scores) >= 2 and spread == 0:
                out.append("scores %s: every read gives the version the same score" % arm)
        if lens.max is not None:
            if strong_scores:
                out.append("scores %s room above the strong anchor: %d (scale maximum %d)"
                           % (arm, lens.max - high_strong, lens.max))
            else:
                out.append("scores %s room above the strong anchor: not assessable "
                           "(scale maximum %d)" % (arm, lens.max))
        if lens.criteria:
            carried = len([x for x in records if x.read.arm == arm
                           and x.read.reader not in not_blind and x.reply is not None
                           and "SCORE" in x.reply.fields])
            out.append("criteria %s: %d replies carried a SCORE field, not read"
                       % (arm, carried))
        if arm in standing.headrooms:
            out.extend(standing.headrooms[arm].lines(arm))
        if plan.calibration_only:
            out.append(_calibration_of(plan, records, not_blind, arm).line(arm))
    out.append("counted lenses: %s" % (" ".join(counted) if counted else "none"))
    if plan.calibration_only:
        out.append("calibration only: no version read")
    else:
        for lens in plan.lenses:
            version = [x for x in records if x.read.arm == lens.arm
                       and x.read.document == VERSION and x.read.reader not in not_blind]
            failed = len([x for x in version if x.status == "failed"])
            not_run = len([x for x in version if x.status not in ("valid", "failed")])
            out.append("missing %s version: %d of %d planned reads (failed %d, not run %d)"
                       % (lens.arm, failed + not_run, len(planned_in(lens.arm, VERSION)),
                          failed, not_run))
    if not [x for x in records if x.status == "valid"]:
        out.append("DEAD: 0 of %d planned reads are valid" % len(reads))

    # rules
    for index, rule in enumerate(rules):
        where = "overall" if rule.lens is None else rule.lens
        label = "rule %s (%s)" % (rule.name, where)
        written = plan.rules[index]
        out.append("%s: %s" % (label, _rule_text(written)))
        outcome = judge(plan, rule, standing.states, counted)
        recs = outcome.recs
        for clause, count in outcome.counts:
            out.append("%s count: %s: %d of %d valid reads" % (label, clause.test(), count,
                                                                len(recs)))
        covered = [x.arm for x in plan.lenses] if rule.lens is None else [rule.lens]
        left_out = sum(len(_valid(pool_records, pool_not_blind, arm, VERSION, pool_not_blind))
                       for arm in covered)
        out.append("%s verdict: %s [not blind: %d reads left out]%s"
                   % (label, outcome.verdict, left_out,
                      " [uncalibrated]" if uncalibrated else ""))
        for reason in outcome.reasons:
            out.append("%s reason: %s" % (label, reason))
        if ext is not None:
            out.append("%s at the pooled reads: %s" % (label, _rule_text(rule)))
            out.append("%s extension: first run %s, pooled %s"
                       % (label, first_verdicts[index], outcome.verdict))
        for kind, clause in rule.clauses:
            out.append(_evidence_line(label, clause, rule, recs, plan.sidedness))
        possible = outcome.possible
        if possible is not None:
            if len(possible) == 1:
                out.append("%s completions (missing reads: %d): settled: %s"
                           % (label, outcome.m, possible[0]))
            else:
                out.append("%s completions (missing reads: %d): unsettled: %s possible"
                           % (label, outcome.m, ", ".join(possible)))
        if plan.replicate_of is not None:
            first_arms = first_counted if rule.lens is None else (
                [rule.lens] if rule.lens in first_counted else [])
            first_recs = [x for x in first_blind if x.read.arm in first_arms
                          and x.read.document == VERSION and x.status == "valid"]
            out.extend(_replicate_lines(label, [c for _k, c in rule.clauses], recs,
                                        first_recs))

    groups = []
    for reader in plan.readers:
        if reader.group is not None and reader.group not in groups:
            groups.append(reader.group)
    for group in groups:
        names = set(r.name for r in plan.readers if r.group == group)
        out.append("reader-group %s: %d valid reads"
                   % (group, len([x for x in records
                                  if x.status == "valid" and x.read.reader in names])))
    out.append(harness.VALIDITY_LINE)
    return harness.finish_result(folder, out, records, log, stopped)


def _rule_text(rule):
    return "; ".join("%s if %s" % (kind, clause.text()) for kind, clause in rule.clauses)
