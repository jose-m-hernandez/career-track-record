"""Reader A/B harness: compare two versions of a career document by reader scores.

The behaviour is stated in docs/specs/reader-ab.md. In short: freeze a plan and its inputs by
hash, check the hashes and that the two versions differ only where the plan says, run the
A/A arm and then each comparison with readers, and score the replies against the frozen
rules. Every function that does work returns a Result, as the other tools do.

This module reads the plan file (``parse``), runs the built-in fake reader inside the tool,
and runs a live reader (a command the user names) only through ``ab_reader_command``.
"""

import difflib
import hashlib
import os
import re
import shlex
from fractions import Fraction

from career_track_record import ab_reader_command, barred, pdf_text

# File names inside a read folder, and in the run folder. Every use goes through these.
READ_A = "A.txt"
READ_B = "B.txt"
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
_show = barred.printed_path

AA = "aa"
LABELS = ("READ", "PRIOR", "SCORE-A", "SCORE-B", "PREFER", "DROVE-IT", "DOUBTS",
          "UNDERSOLD", "OVEREXPLAINED", "OWNED", "FLAG-FIXES")
FREE_TEXT_FIELDS = ("DROVE-IT", "DOUBTS", "UNDERSOLD", "OVEREXPLAINED", "OWNED",
                    "FLAG-FIXES", "PREFER")
STRENGTHS = ("slightly", "clearly", "strongly")
STRONG = ("clearly", "strongly")

PROMPT = """You are reading a résumé for a job. You know nothing about the candidate
beyond what is in these files. Do not guess or use outside knowledge.

Your folder holds four files:
  POSTING.txt  the job posting
  A.txt        one version of the résumé
  B.txt        another version of the same résumé
  PROMPT.txt   this text

Nothing tells you which version is older, newer or preferred. Judge each
on its own against the posting.

Read the posting, then A, then B. Answer on standard output only. Write
these eleven fields, in this order, each starting its own line as
FIELD: value. No bullets, bold, indentation or text before the first
field or after the last. A value may continue on later lines; the next
field name starts a new line. If any field except PRIOR has nothing to
say, write none.

READ: anything; this value is not checked
PRIOR: what you knew about the candidate before reading. If nothing, write exactly: nothing
SCORE-A: a whole number from 1 to 10, as digits only (10 is best)
SCORE-B: the same, for B
PREFER: A, B or TIE (see below)
DROVE-IT: what in the documents decided your preference
DOUBTS: what made you doubt the candidate
UNDERSOLD: what the candidate has but did not make the most of
OVEREXPLAINED: what took more space or words than it earned
OWNED: what the candidate clearly did or led themselves
FLAG-FIXES: changes you would suggest, as text only; nothing is applied

PREFER, first line only: write A or B, then a comma and a space, then
slightly, clearly or strongly, for example "PREFER: B, clearly". You may
add a comma and a short reason on the same line. For no preference write
"PREFER: TIE", optionally followed by a reason. A tie takes no strength.
"""


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


# ------------------------------------------------------------------ the plan model

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


class FakeRule(object):
    """One rule of the fake reader. Build one with the class methods below.

    ``arms`` names the arms it applies to ("aa", "c1", "c2", ...); by default every
    comparison and not the A/A arm. ``on_reads`` is a set of read numbers counted across
    the arm; a preference rule gives TIE on every other read of the arm."""

    PREFERENCE_KINDS = ("containing", "not-containing", "tie", "slot", "random")

    def __init__(self, kind, text=None, field=None, slot=None, seed=None,
                 strength="slightly", arms=None, on_reads=None, non_tie=False,
                 scores=None):
        if strength not in STRENGTHS:
            raise ValueError("unknown strength %r" % (strength,))
        if field is not None and field not in LABELS:
            raise ValueError("unknown field %r" % (field,))
        if kind == "slot" and slot not in ("A", "B"):
            raise ValueError("slot must be A or B")
        self.kind = kind
        self.text = text
        self.field = field
        self.slot = slot
        self.seed = seed
        self.strength = strength
        self.arms = None if arms is None else frozenset(arms)
        self.on_reads = None if on_reads is None else frozenset(on_reads)
        self.non_tie = non_tie
        self.scores = scores

    @classmethod
    def prefer_containing(cls, text, **mods):
        return cls("containing", text=text, **mods)

    @classmethod
    def prefer_not_containing(cls, text, **mods):
        return cls("not-containing", text=text, **mods)

    @classmethod
    def tie(cls, **mods):
        return cls("tie", **mods)

    @classmethod
    def prefer_slot(cls, slot, **mods):
        return cls("slot", slot=slot, **mods)

    @classmethod
    def random(cls, seed, **mods):
        return cls("random", seed=seed, **mods)

    @classmethod
    def write(cls, field, text, **mods):
        return cls("write", field=field, text=text, **mods)

    @classmethod
    def omit(cls, field, **mods):
        return cls("omit", field=field, **mods)

    @classmethod
    def score(cls, a, b, **mods):
        return cls("score", scores=(a, b), **mods)

    def preference(self):
        return self.kind in self.PREFERENCE_KINDS


class Clause(object):
    """"VERSION in K of N" (n given) or "VERSION in K or more" (n is None)."""

    def __init__(self, version, k, n=None):
        self.version = version
        self.k = k
        self.n = n

    def text(self):
        if self.n is None:
            return "%s preferred in %d or more" % (self.version, self.k)
        return "%s preferred in %d of %d" % (self.version, self.k, self.n)


class Hypothesis(object):
    """A decision rule for one comparison (numbered from 1). ``clauses`` is an ordered list
    of (verdict, Clause) with verdict SUPPORTED or REFUTED; the first that holds decides, and
    when none holds the verdict is INCONCLUSIVE. ``name`` is h1, h2, ... in plan order."""

    def __init__(self, name, comparison, clauses=()):
        self.name = name
        self.comparison = comparison
        self.clauses = list(clauses)


class Mechanism(object):
    """A pattern matched in the reply fields of one comparison's arm; SUPPORTED at K or more
    matching replies. ``fields`` defaults to every free-text field. ``name`` is the pattern."""

    def __init__(self, name, comparison, pattern, k, fields=None):
        self.name = name
        self.comparison = comparison
        self.pattern = pattern
        self.k = k
        self.fields = tuple(FREE_TEXT_FIELDS if fields is None else fields)


class Plan(object):
    """The plan as an object. ``versions`` is an ordered list of (name, path),
    ``comparisons`` an ordered list of (first name, second name) and ``change_scope`` a list
    of (comparison number or None, pattern). Relative paths are relative to the folder that
    holds the plan file."""

    def __init__(self, posting, versions, comparisons, readers, fake_rules=(),
                 reads_per_reader=3, hypotheses=(), mechanisms=(), change_scope=(),
                 noise_threshold=Fraction(1, 2), spend_ceiling=None, aa_version=None,
                 amends=None, read_timeout=DEFAULT_READ_TIMEOUT):
        self.posting = posting
        self.versions = list(versions)
        self.comparisons = list(comparisons)
        self.readers = list(readers)
        self.fake_rules = list(fake_rules)
        self.reads_per_reader = reads_per_reader
        self.hypotheses = list(hypotheses)
        self.mechanisms = list(mechanisms)
        self.change_scope = list(change_scope)
        self.noise_threshold = noise_threshold
        self.spend_ceiling = spend_ceiling
        self.aa_version = aa_version
        self.amends = amends
        self.read_timeout = read_timeout

    def version_path(self, name):
        for version, path in self.versions:
            if version == name:
                return path
        return None

    def effective_aa_version(self):
        """The A/A version: the named one, else the second version of the first comparison."""
        if self.aa_version is not None:
            return self.aa_version
        return self.comparisons[0][1]

    def reads_per_arm(self):
        return len(self.readers) * self.reads_per_reader

    def live_readers(self):
        return [r for r in self.readers if r.kind == "live"]


# ------------------------------------------------------------------ the plan file

class PlanError(Exception):
    """The plan file cannot be used. ``problems`` is a list of one-line messages."""

    def __init__(self, problems):
        Exception.__init__(self, "; ".join(problems))
        self.problems = list(problems)


_LIST_KEYS = ("versions", "comparisons", "readers", "hypotheses", "mechanisms",
              "change-scope", "fake-reader")
_SCALAR_KEYS = ("posting", "aa-version", "reads-per-reader", "noise-threshold",
                "spend-ceiling", "amends", "read-timeout")
_NAME = re.compile(r"[A-Za-z0-9-]+\Z")
_INTEGER = re.compile(r"[0-9]+\Z")
_SIGNED = re.compile(r"-?[0-9]+\Z")
_FRACTION = re.compile(r"([0-9]+)/([0-9]+)\Z")
_COMPARISON = re.compile(r"(\S+) vs (\S+)\Z")
_CLAUSE = re.compile(r"(SUPPORTED|REFUTED) if (\S+) (?:is )?preferred in "
                     r"(?:([0-9]+) of ([0-9]+)|([0-9]+) or more)\Z")
_SUPPORTED_AT = re.compile(r"supported at ([0-9]+) or more\Z")
_READ_K = re.compile(r"read ([0-9]+)\Z")
_QUOTED = r'"(.+)"'


class _Parse(object):
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
        if not _INTEGER.match(text) or int(text) < minimum:
            what = "a positive whole number" if minimum else "a whole number, 0 or more"
            self.bad(number, "%s must be %s" % (key, what))
            return None
        return int(text)

    def pattern(self, number, text, flags=0):
        try:
            re.compile(text, flags)
        except re.error:
            self.bad(number, "not a valid pattern: %s" % _show(text))
            return False
        return True


def parse(path):
    """Read a plan file and return a Plan. Raises PlanError, naming each problem with the
    plan line number where there is one."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (OSError, ValueError):
        raise PlanError(["cannot read the plan: %s" % _show(os.path.basename(path))])
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise PlanError(["the plan is not valid UTF-8: %s" % _show(os.path.basename(path))])
    return parse_text(text)


def _structure(state, text):
    """(scalars, lists): scalars maps a key to (line, value), lists a key to [(line, item)]."""
    scalars, lists = {}, {}
    seen = set()
    current = None
    for number, raw in enumerate(_LINE_BREAK.split(text), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw[0] in " \t":
            if current is None:
                state.bad(number, "an indented line that belongs to no key")
            elif current in _SCALAR_KEYS:
                state.bad(number, "%s takes one value on its own line, not a list" % current)
            elif current in _LIST_KEYS:
                lists[current].append((number, stripped))
            continue
        key, colon, value = stripped.partition(":")
        key, value = key.strip(), value.strip()
        if not colon:
            state.bad(number, "not a key: value line")
            current = None
            continue
        if key not in _LIST_KEYS and key not in _SCALAR_KEYS:
            state.bad(number, "unknown key %s" % _short(key))
            current = "?"
            continue
        if key in seen:
            state.bad(number, "the key %s is given twice" % key)
            current = "?"
            continue
        seen.add(key)
        current = key
        if key in _LIST_KEYS:
            lists[key] = []
            if value:
                state.bad(number, "%s is a list: write its items on indented lines" % key)
        elif not value:
            state.bad(number, "%s needs a value" % key)
        else:
            scalars[key] = (number, value)
    return scalars, lists


def _short(text):
    """Text from the plan as it is shown in a message: cut to 40 characters, then escaped."""
    return _show(text if len(text) <= 40 else text[:40] + "...")


def parse_text(text):
    """The work of ``parse``, on the text of a plan."""
    state = _Parse()
    scalars, lists = _structure(state, text)

    # versions
    versions = []
    names = set()
    for number, item in lists.get("versions", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) != 2:
            state.bad(number, "a version is written: name | file")
        elif not _NAME.match(parts[0]):
            state.bad(number, "a name holds letters, digits and - only: %s" % _short(parts[0]))
        elif parts[0] in names:
            state.bad(number, "the version %s is named twice" % parts[0])
        else:
            names.add(parts[0])
            versions.append((parts[0], parts[1]))

    # comparisons
    comparisons, comparison_text = [], []
    for number, item in lists.get("comparisons", []):
        match = _COMPARISON.match(item)
        if not match:
            state.bad(number, "a comparison is written: X vs Y")
        elif match.group(1) not in names or match.group(2) not in names:
            state.bad(number, "a comparison names a version the plan does not have")
        elif item in comparison_text:
            state.bad(number, "the comparison %s is named twice" % item)
        else:
            comparisons.append((match.group(1), match.group(2)))
            comparison_text.append(item)

    def which_comparison(number, parts, what):
        """(comparison number, rest of the fields), or None with a problem recorded."""
        if len(parts) > 1 and parts[0] in comparison_text:
            return comparison_text.index(parts[0]) + 1, parts[1:]
        if len(comparison_text) == 1:
            return 1, parts
        if len(comparison_text) > 1:
            state.bad(number, "%s must start with its comparison, written as in "
                      "comparisons" % what)
        return None

    # scalars
    posting = None
    if "posting" in scalars:
        posting = scalars["posting"][1]
    aa_version = None
    if "aa-version" in scalars:
        number, value = scalars["aa-version"]
        if value in names:
            aa_version = value
        else:
            state.bad(number, "aa-version names the unknown version %s" % _short(value))
    reads_per_reader = 3
    if "reads-per-reader" in scalars:
        number, value = scalars["reads-per-reader"]
        got = state.integer(number, "reads-per-reader", value, minimum=1)
        reads_per_reader = got if got is not None else 3
    noise = Fraction(1, 2)
    if "noise-threshold" in scalars:
        number, value = scalars["noise-threshold"]
        match = _FRACTION.match(value)
        if not match or int(match.group(2)) == 0:
            state.bad(number, "noise-threshold is written as a fraction n/d")
        else:
            noise = Fraction(int(match.group(1)), int(match.group(2)))
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

    # readers
    readers, reader_names = [], set()
    for number, item in lists.get("readers", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) < 2:
            state.bad(number, "a reader is written: name | command")
            continue
        name, command = parts[0], parts[1]
        if not _NAME.match(name):
            state.bad(number, "a name holds letters, digits and - only: %s" % _short(name))
            continue
        if name in reader_names:
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
                          "each: %s" % _short(extra))
                ok = False
        if command != FAKE:
            try:
                if not shlex.split(command):
                    raise ValueError("empty")
            except ValueError:
                state.bad(number, "the reader command cannot be split into words")
                ok = False
        if ok:
            reader_names.add(name)
            readers.append(Reader(name, command, not_blind, cost if command != FAKE else 1))

    # hypotheses
    hypotheses = []
    for number, item in lists.get("hypotheses", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        found = which_comparison(number, parts, "a hypothesis")
        if found is None:
            continue
        comparison, rest = found
        if len(rest) != 1:
            state.bad(number, "a hypothesis is written: [comparison |] rule")
            continue
        clauses = _hypothesis_clauses(state, number, rest[0], comparisons[comparison - 1])
        if clauses is not None:
            hypotheses.append(Hypothesis("h%d" % (len(hypotheses) + 1), comparison, clauses))

    # mechanisms
    mechanisms = []
    for number, item in lists.get("mechanisms", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        found = which_comparison(number, parts, "a mechanism")
        if found is None:
            continue
        comparison, rest = found
        if len(rest) != 3:
            state.bad(number, "a mechanism is written: [comparison |] pattern | fields | "
                      "supported at <n> or more")
            continue
        pattern, fields_text, rule = rest
        fields = None
        ok = state.pattern(number, pattern, re.I)
        if fields_text != "default":
            fields = [f.strip() for f in fields_text.split(",")]
            bad = [f for f in fields if f not in FREE_TEXT_FIELDS]
            if bad:
                state.bad(number, "not a reply field a pattern can match: %s" % _short(bad[0]))
                ok = False
        match = _SUPPORTED_AT.match(rule)
        if not match or int(match.group(1)) < 1:
            state.bad(number, "the last field is: supported at <n> or more")
            ok = False
        if ok:
            mechanisms.append(Mechanism(pattern, comparison, pattern, int(match.group(1)),
                                        fields))

    # change scope
    change_scope = []
    for number, item in lists.get("change-scope", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        comparison = None
        if len(parts) == 2 and parts[0] in comparison_text:
            comparison = comparison_text.index(parts[0]) + 1
            parts = parts[1:]
        if len(parts) != 1:
            state.bad(number, "a change-scope item is written: [comparison |] pattern")
        elif state.pattern(number, parts[0]):
            if re.fullmatch(parts[0], "") or re.search(parts[0], ""):
                state.bad(number, "a change-scope pattern must not match empty text")
            else:
                change_scope.append((comparison, parts[0]))

    # the fake reader
    has_fake = any(r.kind == "fake" for r in readers)
    reads = len(readers) * reads_per_reader
    rules, rule_lines = [], []
    for number, item in lists.get("fake-reader", []):
        rule = _fake_rule(state, number, item, comparison_text, reads)
        if rule is not None:
            rules.append(rule)
            rule_lines.append(number)
    if rules and not has_fake:
        state.bad(rule_lines[0], "fake-reader rules, but the plan has no fake reader")
    _preference_overlaps(state, rules, rule_lines, len(comparisons), reads)

    # what the plan must have
    if "posting" not in scalars:
        state.problems.append("the plan names no posting")
    if not versions:
        state.problems.append("the plan names no version")
    if not comparisons:
        state.problems.append("the plan has no comparison")
    if not readers and not [1 for number, _item in lists.get("readers", [])]:
        state.problems.append("the plan has no reader")
    if state.problems:
        raise PlanError(state.problems)
    return Plan(posting, versions, comparisons, readers, fake_rules=rules,
                reads_per_reader=reads_per_reader, hypotheses=hypotheses,
                mechanisms=mechanisms, change_scope=change_scope, noise_threshold=noise,
                spend_ceiling=ceiling, aa_version=aa_version, amends=amends,
                read_timeout=timeout)


def _hypothesis_clauses(state, number, rule, pair):
    """The ordered (verdict, Clause) list of a hypothesis rule, or None."""
    pieces = rule.split("; ")
    if pieces[-1] != "otherwise INCONCLUSIVE":
        state.bad(number, "a hypothesis rule ends with: otherwise INCONCLUSIVE")
        return None
    clauses = []
    ok = True
    for piece in pieces[:-1]:
        match = _CLAUSE.match(piece)
        if not match:
            state.bad(number, "a clause is written: SUPPORTED (or REFUTED) if <version> "
                      "preferred in <n> of <m> (or <n> or more): %s" % _short(piece))
            ok = False
            continue
        verdict, version = match.group(1), match.group(2)
        if version not in pair:
            state.bad(number, "the hypothesis names %s, which is not in its comparison"
                      % _short(version))
            ok = False
            continue
        if match.group(5) is not None:
            clauses.append((verdict, Clause(version, int(match.group(5)))))
        elif int(match.group(3)) > int(match.group(4)):
            state.bad(number, "%s of %s asks for more reads than it counts"
                      % (match.group(3), match.group(4)))
            ok = False
        else:
            clauses.append((verdict, Clause(version, int(match.group(3)),
                                            int(match.group(4)))))
    if ok and not clauses:
        state.bad(number, "a hypothesis rule needs at least one SUPPORTED or REFUTED clause")
        return None
    return clauses if ok else None


def _fake_rule(state, number, item, comparison_text, reads):
    """One FakeRule from a fake-reader item, or None with a problem recorded."""
    parts = state.fields(number, item)
    if parts is None:
        return None
    arms = None
    if len(parts) > 1 and (parts[0] in ("all", AA) or parts[0] in comparison_text):
        if parts[0] == AA:
            arms = [AA]
        elif parts[0] != "all":
            arms = ["c%d" % (comparison_text.index(parts[0]) + 1)]
        parts = parts[1:]
    rule_text, extras = parts[0], parts[1:]
    strength, on_read = None, None
    for index, extra in enumerate(extras):
        match = _READ_K.match(extra)
        if extra in STRENGTHS and strength is None and on_read is None and index == 0:
            strength = extra
        elif match and on_read is None and index == len(extras) - 1:
            on_read = int(match.group(1))
        else:
            state.bad(number, "after the rule come [| strength] [| read <k>]: %s"
                      % _short(extra))
            return None
    if on_read is not None and not 1 <= on_read <= reads:
        state.bad(number, "read %d is outside the arm's reads (1 to %d)" % (on_read, reads))
        return None
    mods = dict(arms=arms, on_reads=None if on_read is None else [on_read])
    if strength is not None:
        mods["strength"] = strength
    rule = _fake_rule_body(state, number, rule_text, mods, strength)
    return rule


def _fake_rule_body(state, number, text, mods, strength):
    match = re.match(r"prefer containing " + _QUOTED + r"\Z", text)
    if match:
        return FakeRule.prefer_containing(match.group(1), **mods)
    match = re.match(r"prefer without " + _QUOTED + r"\Z", text)
    if match:
        return FakeRule.prefer_not_containing(match.group(1), **mods)
    if text == "tie":
        if strength is not None:
            state.bad(number, "tie takes no strength")
            return None
        return FakeRule.tie(**mods)
    match = re.match(r"prefer slot ([AB])\Z", text)
    if match:
        return FakeRule.prefer_slot(match.group(1), **mods)
    match = re.match(r"random seed (-?[0-9]+)( non-tie)?\Z", text)
    if match:
        return FakeRule.random(int(match.group(1)), non_tie=bool(match.group(2)), **mods)
    match = re.match(r"write " + _QUOTED + r" in ([A-Z-]+)\Z", text)
    if match:
        if match.group(2) not in LABELS:
            state.bad(number, "not a reply field: %s" % _short(match.group(2)))
            return None
        return FakeRule.write(match.group(2), match.group(1), **mods)
    match = re.match(r"omit ([A-Z-]+)\Z", text)
    if match:
        if match.group(1) not in LABELS:
            state.bad(number, "not a reply field: %s" % _short(match.group(1)))
            return None
        return FakeRule.omit(match.group(1), **mods)
    match = re.match(r"score (-?[0-9]+) (-?[0-9]+)\Z", text)
    if match:
        return FakeRule.score(int(match.group(1)), int(match.group(2)), **mods)
    state.bad(number, "not a fake-reader rule: %s" % _short(text))
    return None


def _preference_overlaps(state, rules, lines, comparison_count, reads):
    """One problem for each pair of preference rules that apply to the same read."""
    all_arms = ["c%d" % n for n in range(1, comparison_count + 1)]
    chosen = [(rule, line) for rule, line in zip(rules, lines) if rule.preference()]
    for i, (first, first_line) in enumerate(chosen):
        for second, second_line in chosen[i + 1:]:
            arms_a = all_arms if first.arms is None else sorted(first.arms)
            arms_b = all_arms if second.arms is None else sorted(second.arms)
            shared = [arm for arm in arms_a if arm in arms_b]
            numbers = range(1, reads + 1)
            both = [n for n in numbers
                    if (first.on_reads is None or n in first.on_reads)
                    and (second.on_reads is None or n in second.on_reads)]
            if shared and both:
                state.bad(second_line, "two preference rules apply to read %d of %s "
                          "(the other is on line %d)" % (both[0], shared[0], first_line))


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
        return "cannot %s %s: %s" % (self.action, _show(self.name), _show(self.reason))


def _reason(exc):
    return getattr(exc, "strerror", None) or exc.__class__.__name__


def _relative(folder, path):
    return os.path.relpath(path, folder)


def _write_new(folder, path, data, taken=False):
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
        raise RunFolderError("write", _relative(folder, path), "File exists")
    except OSError as exc:
        raise RunFolderError("write", _relative(folder, path), _reason(exc))


def _read_bytes(folder, path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise RunFolderError("read", _relative(folder, path), _reason(exc))


def _listdir(folder, path):
    try:
        return os.listdir(path)
    except OSError as exc:
        raise RunFolderError("read", _relative(folder, path), _reason(exc))


def _folder(plan_path):
    return os.path.dirname(os.path.abspath(plan_path))


def _sha256_file(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except (OSError, ValueError):
        return None


def prompt_sha256():
    return hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()


def _inputs(plan, plan_path):
    """Ordered (label, absolute path) of the plan file and every input it names."""
    folder = _folder(plan_path)
    items = [(os.path.basename(plan_path), os.path.abspath(plan_path)),
             (plan.posting, os.path.join(folder, plan.posting))]
    for _name, path in plan.versions:
        items.append((path, os.path.join(folder, path)))
    if plan.amends is not None:
        items.append((plan.amends, os.path.join(folder, plan.amends)))
    seen = set()
    unique = []
    for label, path in items:
        if label not in seen:
            seen.add(label)
            unique.append((label, path))
    return unique


def _freeze_files(folder):
    return sorted(n for n in _listdir(folder, folder) if n.endswith(FREEZE_SUFFIX))


def _reply_files(folder):
    """The reply files the run folder holds, as reads/<arm>/<k>/REPLY.txt."""
    found = []
    reads = os.path.join(folder, READS_DIR)
    if os.path.isdir(reads):
        for arm in sorted(_listdir(folder, reads)):
            arm_dir = os.path.join(reads, arm)
            if not os.path.isdir(arm_dir):
                continue
            for number in sorted(_listdir(folder, arm_dir)):
                if os.path.isfile(os.path.join(arm_dir, number, READ_REPLY)):
                    found.append("%s/%s/%s/%s" % (READS_DIR, arm, number, READ_REPLY))
    return found


def freeze(plan_path):
    """Read the plan, hash it and every input it names, and write the freeze file beside it.
    Every plan problem is found here."""
    try:
        return _freeze(plan_path)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def _freeze(plan_path):
    try:
        plan = parse(plan_path)
    except PlanError as exc:
        return Result(2, False, error="\n".join(exc.problems))
    problems = []
    folder = _folder(plan_path)
    hashes = []
    for label, path in _inputs(plan, plan_path):
        digest = _sha256_file(path) if os.path.isfile(path) else None
        if digest is None:
            problems.append("missing input: %s" % _show(label))
        hashes.append((label, digest))
    hashes.append((PROMPT_LABEL, prompt_sha256()))
    for name in _freeze_files(folder):
        problems.append("a freeze file already exists: %s" % _show(name))
    for name in _reply_files(folder):
        problems.append("the run folder already holds a reply: %s" % _show(name))
    if problems:
        return Result(2, False, error="\n".join(problems))
    name = os.path.basename(plan_path) + FREEZE_SUFFIX
    _write_new(folder, os.path.join(folder, name),
               "".join("%s  %s\n" % (digest, label) for label, digest in hashes))
    return Result(0, True, text="freeze written: %s\n" % _show(name))


def _read_freeze(path):
    """The freeze file's (label, digest) pairs, in file order."""
    entries = []
    with open(path, encoding="utf-8") as handle:
        for line in handle.read().split("\n"):
            if line and not line.startswith("#") and "  " in line:
                digest, label = line.split("  ", 1)
                entries.append((label, digest))
    return entries


def _verify(plan_path, with_prompt):
    """Check the freeze against the files. Returns (plan or None, problems, recorded hashes
    by label, hash of the freeze file). The plan is parsed only when its own hash matches
    the freeze, so a plan edited after the freeze is named and never read."""
    folder = _folder(plan_path)
    freeze_path = plan_path + FREEZE_SUFFIX
    freeze_name = os.path.basename(freeze_path)
    if not os.path.isfile(freeze_path):
        return None, ["no freeze file: %s" % _show(freeze_name)], {}, None
    try:
        entries = _read_freeze(freeze_path)
    except (OSError, UnicodeDecodeError):
        return None, ["cannot read the freeze file: %s" % _show(freeze_name)], {}, None
    recorded = dict(entries)
    freeze_hash = _sha256_file(freeze_path)
    plan_label = os.path.basename(plan_path)
    problems = []

    def compare(label, digest):
        if label == PROMPT_LABEL:
            if with_prompt and digest != prompt_sha256():
                problems.append("changed since the freeze: %s" % _show(label))
            return
        path = os.path.join(folder, label)
        now = _sha256_file(path) if os.path.isfile(path) else None
        if now is None:
            problems.append("missing input: %s" % _show(label))
        elif now != digest:
            problems.append("changed since the freeze: %s" % _show(label))

    plan_now = _sha256_file(plan_path) if os.path.isfile(plan_path) else None
    if plan_label not in recorded or plan_now != recorded[plan_label]:
        if plan_label not in recorded:
            problems.append("not covered by the freeze: %s" % _show(plan_label))
        for label, digest in entries:
            compare(label, digest)
        return None, problems, recorded, freeze_hash
    try:
        plan = parse(plan_path)
    except PlanError as exc:
        return None, list(exc.problems), recorded, freeze_hash
    expected = _inputs(plan, plan_path)
    for label, _path in expected:
        if label not in recorded:
            problems.append("not covered by the freeze: %s" % _show(label))
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
            problems.append("the freeze names a file the plan does not: %s" % _show(label))
    return plan, problems, recorded, freeze_hash


# ------------------------------------------------------------------ the isolation check

_SPACES = re.compile(r"[ \t]+")
_LINE_BREAK = re.compile(r"\r\n|\r|\n")


def collapsed_lines(text):
    """Lines with each run of spaces and tabs made one space, stripped, blanks dropped."""
    lines = []
    for raw in _LINE_BREAK.split(text):
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


def _arms(plan):
    """(arm id, first version, second version): the A/A arm, then each comparison."""
    aa = plan.effective_aa_version()
    arms = [(AA, aa, aa)]
    for index, (first, second) in enumerate(plan.comparisons, 1):
        arms.append(("c%d" % index, first, second))
    return arms


def _isolation_problems(plan, plan_path):
    folder = _folder(plan_path)
    problems = []
    texts = {}

    def lines_of(name):
        label = plan.version_path(name)
        if name not in texts:
            path = os.path.join(folder, label)
            if not os.path.isfile(path):
                texts[name] = None  # reported as a missing input by the hash stage
            else:
                try:
                    texts[name] = collapsed_lines(read_text(path))
                except Unreadable as exc:
                    problems.append("cannot read %s: %s" % (_show(label), exc))
                    texts[name] = None
        return texts[name]

    for index, (arm, first, second) in enumerate(_arms(plan)):
        a, b = lines_of(first), lines_of(second)
        if a is None or b is None:
            continue
        changes = changed_lines(a, b)
        label = "%s (%s vs %s)" % (arm, first, second)
        if arm == AA:
            if changes:
                problems.append("%s: the A/A arm shows a changed line" % label)
            continue
        if not changes:
            problems.append("%s: no changed line; a file compared with itself is the "
                            "control, not a test" % label)
            continue
        scope = [pattern for comparison, pattern in plan.change_scope
                 if comparison in (None, index)]
        for mark, line in changes:
            if not any(re.search(pattern, line) for pattern in scope):
                problems.append("%s: changed line outside the change scope: %s %s"
                                % (arm, mark, _show(line)))
    return problems


# ------------------------------------------------------------------ reply format

_LABEL_LINE = re.compile(r"^(%s):(.*)$" % "|".join(LABELS))
_PREFER_PICK = re.compile(r"(A|B)\s*,\s*(slightly|clearly|strongly)(?![A-Za-z0-9])(.*)\Z",
                          re.S)
_PREFER_TIE = re.compile(r"TIE(?![A-Za-z0-9])(.*)\Z", re.S)
_WHOLE = re.compile(r"-?[0-9]+\Z")
_RATIONALE_EDGE = " ,;:-–—"


class Reply(object):
    """A parsed reply. ``failure`` is None for a valid read, else the reason it failed.
    ``prior_flag`` is None only when PRIOR is exactly ``nothing``."""

    def __init__(self):
        self.fields = {}
        self.failure = None
        self.read_id = None
        self.score_a = None
        self.score_b = None
        self.choice = None
        self.strength = None
        self.rationale = ""
        self.prior_flag = None


def _parse_prefer(line):
    """(choice, strength, rationale) from the first line of PREFER, or None."""
    value = line.strip()
    match = _PREFER_PICK.match(value)
    if match:
        return match.group(1), match.group(2), match.group(3).strip().lstrip(_RATIONALE_EDGE)
    match = _PREFER_TIE.match(value)
    if match:
        return "TIE", None, match.group(1).strip().lstrip(_RATIONALE_EDGE)
    return None


def _score(value):
    if _WHOLE.match(value):
        return int(value)
    return None


def parse_reply(text):
    """Parse a reply. A field starts a line as ``FIELD: value`` (case-sensitive) and runs to
    the next line that starts with a field name; text before the first field is ignored."""
    reply = Reply()
    parts = {}
    repeated = []
    current = None
    for line in _LINE_BREAK.split(text):
        match = _LABEL_LINE.match(line)
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
    reply.fields = dict((k, "\n".join(v).strip()) for k, v in parts.items())
    fields = reply.fields
    prior = fields.get("PRIOR")
    if prior is None:
        reply.prior_flag = "PRIOR missing"
    elif prior != "nothing":
        reply.prior_flag = "PRIOR is not nothing: %s" % prior
    if repeated:
        reply.failure = "%s appears twice" % repeated[0]
        return reply
    for label in ("READ", "SCORE-A", "SCORE-B", "PREFER"):
        if label not in fields:
            reply.failure = "missing %s" % label
            return reply
    reply.read_id = fields["READ"]
    reply.score_a = _score(fields["SCORE-A"])
    reply.score_b = _score(fields["SCORE-B"])
    if reply.score_a is None:
        reply.failure = "SCORE-A is not an integer"
    elif reply.score_b is None:
        reply.failure = "SCORE-B is not an integer"
    else:
        picked = _parse_prefer(parts["PREFER"][0])
        if picked is None:
            reply.failure = "PREFER cannot be read"
        else:
            reply.choice, reply.strength, reply.rationale = picked
    return reply


# ------------------------------------------------------------------ the fake reader

class PlannedRead(object):
    def __init__(self, arm, number, reader, slot_a, slot_b):
        self.arm = arm
        self.number = number
        self.reader = reader
        self.slot_a = slot_a
        self.slot_b = slot_b

    @property
    def id(self):
        return "%s/%d" % (self.arm, self.number)


def _planned_reads(plan):
    reads = []
    for arm, first, second in _arms(plan):
        number = 0
        for reader in plan.readers:
            for _ in range(plan.reads_per_reader):
                number += 1
                a, b = (first, second) if number % 2 == 1 else (second, first)
                reads.append(PlannedRead(arm, number, reader.name, a, b))
    return reads


def _applies(rule, read):
    if rule.arms is None:
        return read.arm != AA
    return read.arm in rule.arms


def _fires(rule, read):
    return _applies(rule, read) and (rule.on_reads is None or read.number in rule.on_reads)


def random_pick(seed, arm, number, non_tie=False):
    """What a seeded random rule picks for read ``number`` of ``arm``: the first byte of the
    sha256 of "<seed>:<arm>:<number>". With ``non_tie`` an even byte is A and an odd byte
    is B. Without it the byte mod 3 is 0 for A, 1 for B and 2 for TIE."""
    digest = hashlib.sha256(("%s:%s:%d" % (seed, arm, number)).encode("utf-8")).digest()
    if non_tie:
        return "A" if digest[0] % 2 == 0 else "B"
    return ("A", "B", "TIE")[digest[0] % 3]


def _preference(rules, read, text_a, text_b):
    """(choice, strength) from the one preference rule that fires on the read (the first, if
    a caller gives more); TIE when none fires."""
    for rule in rules:
        if not rule.preference() or not _fires(rule, read):
            continue
        if rule.kind == "tie":
            return "TIE", None
        if rule.kind == "slot":
            return rule.slot, rule.strength
        if rule.kind == "random":
            pick = random_pick(rule.seed, read.arm, read.number, rule.non_tie)
            return (pick, None) if pick == "TIE" else (pick, rule.strength)
        in_a, in_b = rule.text in text_a, rule.text in text_b
        if rule.kind == "not-containing":
            in_a, in_b = not in_a, not in_b
        if in_a and not in_b:
            return "A", rule.strength
        if in_b and not in_a:
            return "B", rule.strength
        return "TIE", None
    return "TIE", None


def fake_reply(read, rules, text_a, text_b):
    """The text of the fake reader's reply to one read."""
    choice, strength = _preference(rules, read, text_a, text_b)
    scores = (5, 5)
    for rule in rules:
        if rule.kind == "score" and _fires(rule, read):
            scores = rule.scores
    values = {"READ": read.id, "PRIOR": "nothing", "SCORE-A": str(scores[0]),
              "SCORE-B": str(scores[1])}
    for label in FREE_TEXT_FIELDS[:-1]:
        values[label] = "none"
    written = set()
    rationale = []
    omitted = set()
    for rule in rules:
        if rule.kind not in ("write", "omit") or not _fires(rule, read):
            continue
        if rule.kind == "omit":
            omitted.add(rule.field)
        elif rule.field == "PREFER":
            rationale.append(rule.text)
        elif rule.field in written:
            values[rule.field] += " " + rule.text
        else:
            values[rule.field] = rule.text
            written.add(rule.field)
    prefer = "TIE" if choice == "TIE" else "%s, %s" % (choice, strength)
    if rationale:
        prefer += " " + " ".join(rationale)
    values["PREFER"] = prefer
    return "".join("%s: %s\n" % (label, values[label]) for label in LABELS
                   if label not in omitted)


# ------------------------------------------------------------------ run

def _costs(plan):
    return dict((reader.name, reader.cost) for reader in plan.readers)


def _live_preview(plan, planned):
    """The text printed by a run that holds live readers and was not given --live."""
    costs = _costs(plan)
    lines = ["live readers are configured: nothing was started and no reply was written; "
             "add --live to run them"]
    for reader in plan.live_readers():
        lines.append("reader %s: %s (cost %d per read)"
                     % (reader.name, _show(reader.command), reader.cost))
    lines.append("planned reads: %d" % len(planned))
    lines.append("estimated spend: %d (the sum of the planned reads' declared costs; "
                 "the tool cannot see real spend)" % sum(costs[r.reader] for r in planned))
    lines.append("spend ceiling: %s" % ("none" if plan.spend_ceiling is None
                                       else plan.spend_ceiling))
    return "".join("%s\n" % line for line in lines)


def _live_read(folder, reader, where, timeout):
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
    _write_new(folder, os.path.join(where, READ_STDERR), done.stderr)
    if done.returncode != 0:
        return "exit status %d" % done.returncode
    _write_new(folder, os.path.join(where, READ_REPLY), done.stdout)
    return None


def run(plan_path, live=False):
    """Check, key, read and score. Writes the key, the reads, the run log and a result."""
    try:
        return _run(plan_path, live)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def _run(plan_path, live):
    folder = _folder(plan_path)
    plan, problems, recorded, freeze_hash = _verify(plan_path, with_prompt=True)
    if plan is not None:
        problems += _isolation_problems(plan, plan_path)
        posting = os.path.join(folder, plan.posting)
        if os.path.isfile(posting):
            try:
                read_text(posting)
            except Unreadable as exc:
                problems.append("cannot read %s: %s" % (_show(plan.posting), exc))
    for name in (READS_DIR, KEY_FILE, RUN_LOG):
        if os.path.exists(os.path.join(folder, name)):
            problems.append("the run folder already holds a run: %s" % name)
    if problems:
        return Result(2, False, error="\n".join(problems))
    planned = _planned_reads(plan)
    if plan.live_readers() and not live:
        return Result(0, True, text=_live_preview(plan, planned))
    costs = _costs(plan)
    readers = dict((reader.name, reader) for reader in plan.readers)

    def text_of(label):
        try:
            return read_text(os.path.join(folder, label))
        except Unreadable as exc:
            raise RunFolderError("read", label, str(exc))

    texts = dict((name, text_of(path)) for name, path in plan.versions)
    posting_text = text_of(plan.posting)
    key_text = "".join("%s\t%s\t%s\t%s\n" % (r.id, r.reader, r.slot_a, r.slot_b)
                       for r in planned)
    _write_new(folder, os.path.join(folder, KEY_FILE), key_text)
    key_hash = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
    spent = 0
    ran = 0
    cut = False
    failures = []
    stopped = None
    try:
        for read in planned:
            if plan.spend_ceiling is not None and spent >= plan.spend_ceiling:
                cut = True
                break
            text_a, text_b = texts[read.slot_a], texts[read.slot_b]
            where = os.path.join(folder, READS_DIR, read.arm, str(read.number))
            try:
                os.makedirs(where)
            except OSError as exc:
                raise RunFolderError("write", _relative(folder, where), _reason(exc))
            _write_new(folder, os.path.join(where, READ_A), text_a)
            _write_new(folder, os.path.join(where, READ_B), text_b)
            _write_new(folder, os.path.join(where, READ_POSTING), posting_text)
            _write_new(folder, os.path.join(where, READ_PROMPT), PROMPT)
            reader = readers[read.reader]
            if reader.kind == "fake":
                _write_new(folder, os.path.join(where, READ_REPLY),
                           fake_reply(read, plan.fake_rules, text_a, text_b))
            else:
                reason = _live_read(folder, reader, where, plan.read_timeout)
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
                 "spend ceiling: %s" % ("none" if plan.spend_ceiling is None
                                        else plan.spend_ceiling),
                 "cut: %s" % ("yes" if cut else "no"),
                 "key sha256: %s" % key_hash]
        lines += ["failure %s: %s" % (read_id, reason) for read_id, reason in failures]
        if stopped is not None:
            lines.append("stopped: %s" % stopped)
        _write_new(folder, os.path.join(folder, RUN_LOG),
                   "".join("%s\n" % line for line in lines))
    if stopped is None:
        return _score_and_write(plan_path, plan, recorded, freeze_hash)
    try:
        return _score_and_write(plan_path, plan, recorded, freeze_hash)
    except RunFolderError as exc:
        return Result(2, False, error="%s\n%s" % (stopped, exc.line))


def score(plan_path):
    """Score the replies in the run folder again, against the frozen plan. Writes a new result."""
    try:
        return _score_run(plan_path)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def _score_run(plan_path):
    plan, problems, recorded, freeze_hash = _verify(plan_path, with_prompt=False)
    folder = _folder(plan_path)
    if plan is not None and not problems:
        for name in (KEY_FILE, RUN_LOG):
            if not os.path.isfile(os.path.join(folder, name)):
                problems.append("the run folder holds no %s" % name)
    if plan is not None and not problems:
        problems += _key_problems(folder)
    if problems:
        return Result(2, False, error="\n".join(problems))
    return _score_and_write(plan_path, plan, recorded, freeze_hash)


def _key_problems(folder):
    """The key is checked against the hash the run log recorded, and must parse."""
    recorded = _load_log(folder).get("key sha256")
    if recorded is None:
        return ["no key sha256 line in %s" % RUN_LOG]
    data = _read_bytes(folder, os.path.join(folder, KEY_FILE))
    if hashlib.sha256(data).hexdigest() != recorded:
        return ["changed since the run: %s" % KEY_FILE]
    try:
        _parse_key(data)
    except KeyParseError as exc:
        return ["cannot parse %s: %s" % (KEY_FILE, exc)]
    return []


# ------------------------------------------------------------------ scoring

class _Rec(object):
    def __init__(self, read, status, reply=None, reason=None):
        self.read = read
        self.status = status  # "valid", "failed" or "not run"
        self.reply = reply
        self.reason = reason


class KeyParseError(Exception):
    pass


def _parse_key(data):
    """The planned reads of a key file's bytes. Raises KeyParseError, saying which line."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise KeyParseError("not valid UTF-8")
    reads = []
    for number, line in enumerate(text.split("\n"), 1):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 4:
            raise KeyParseError("line %d does not hold four fields separated by tabs" % number)
        arm, slash, count = fields[0].rpartition("/")
        if not arm or not slash or not _INTEGER.match(count):
            raise KeyParseError("line %d does not start with a read such as c1/3" % number)
        reads.append(PlannedRead(arm, int(count), fields[1], fields[2], fields[3]))
    return reads


def _load_key(folder):
    data = _read_bytes(folder, os.path.join(folder, KEY_FILE))
    try:
        return _parse_key(data)
    except KeyParseError as exc:
        raise RunFolderError("parse", KEY_FILE, str(exc))


def _load_log(folder):
    log = {}
    data = _read_bytes(folder, os.path.join(folder, RUN_LOG))
    for line in data.decode("utf-8", errors="replace").split("\n"):
        if ": " in line:
            label, value = line.split(": ", 1)
            log[label] = value
    return log


def _records(folder, reads, unrun, failures):
    records = []
    for read in reads:
        path = os.path.join(folder, READS_DIR, read.arm, str(read.number), READ_REPLY)
        if read.id in failures:
            records.append(_Rec(read, "failed", reason=failures[read.id]))
            continue
        if not os.path.isfile(path):
            if unrun:
                records.append(_Rec(read, "not run"))
            else:
                records.append(_Rec(read, "failed", reason="no reply file"))
            continue
        text = _read_bytes(folder, path).decode("utf-8", errors="replace")
        reply = parse_reply(text)
        if reply.failure:
            records.append(_Rec(read, "failed", reply, reply.failure))
        else:
            records.append(_Rec(read, "valid", reply))
    return records


def _pick(rec):
    """(version picked or None, slot picked or None) for a valid read."""
    choice = rec.reply.choice
    if choice == "A":
        return rec.read.slot_a, "A"
    if choice == "B":
        return rec.read.slot_b, "B"
    return None, None


def _percent(part, whole):
    return "%.0f%%" % (100.0 * part / whole)


def _mean(total, count):
    return "%.2f" % (float(total) / count)


def _clause_holds(clause, valid, picks):
    if clause is None:
        return False
    if clause.n is None:
        return picks.get(clause.version, 0) >= clause.k
    return valid == clause.n and picks.get(clause.version, 0) >= clause.k


def _score_and_write(plan_path, plan, recorded, freeze_hash):
    folder = _folder(plan_path)
    log = _load_log(folder)
    cut = log.get("cut") == "yes"
    stopped = log.get("stopped")
    reads = _load_key(folder)
    failures = dict((label[len("failure "):], value) for label, value in log.items()
                    if label.startswith("failure "))
    records = _records(folder, reads, cut or stopped is not None, failures)
    arms = _arms(plan)
    not_blind = set(r.name for r in plan.readers if r.not_blind)
    out = []
    problems = []

    out.append("plan sha256: %s" % _show(recorded.get(os.path.basename(plan_path), "unknown")))
    out.append("freeze sha256: %s" % freeze_hash)
    if plan.amends is not None:
        out.append("amended freeze sha256: %s" % _show(recorded.get(plan.amends, "unknown")))
    out.append("prompt sha256: %s" % _show(recorded.get(PROMPT_LABEL, "unknown")))
    aa_version = plan.effective_aa_version()
    out.append("A/A arm: added by the tool, using version %s" % aa_version)
    if plan.aa_version is None:
        out.append("A/A version: the default, the second version of the first comparison")
    else:
        out.append("A/A version: named by aa-version in the plan")
    for r in reads:
        out.append("key %s: reader=%s A=%s B=%s" % (_show(r.id), _show(r.reader),
                                                    _show(r.slot_a), _show(r.slot_b)))
    for arm, first, second in arms[1:]:
        for reader in plan.readers:
            mine = [r for r in reads if r.arm == arm and r.reader == reader.name]
            first_in_a = len([r for r in mine if r.slot_a == first])
            out.append("slot split %s %s: %s in slot A %d, %s in slot A %d"
                       % (arm, reader.name, first, first_in_a, second,
                          len(mine) - first_in_a))

    for rec in records:
        r = rec.read
        head = "read %s: reader=%s A=%s B=%s" % (_show(r.id), _show(r.reader),
                                                 _show(r.slot_a), _show(r.slot_b))
        flags = []
        if r.reader in not_blind:
            flags.append("not-blind reader")
        if rec.status == "valid":
            if rec.reply.prior_flag:
                flags.append(_show(rec.reply.prior_flag))
            choice = rec.reply.choice
            if choice != "TIE":
                choice = "%s, %s" % (choice, rec.reply.strength)
            out.append("%s scores=%d/%d prefer=%s flags=%s" % (
                head, rec.reply.score_a, rec.reply.score_b, choice,
                "; ".join(flags) if flags else "none"))
        elif rec.status == "failed":
            out.append("%s FAILED (%s)" % (head, _show(rec.reason)))
        else:
            out.append("%s not run" % head)

    def valid_in(arm, only=None):
        return [x for x in records if x.read.arm == arm and x.status == "valid"
                and (only is None or x.read.reader in only)]

    def picks_in(recs):
        picks = {}
        ties = 0
        for x in recs:
            version, _slot = _pick(x)
            if version is None:
                ties += 1
            else:
                picks[version] = picks.get(version, 0) + 1
        return picks, ties

    # reads, all readers and not-blind readers
    for arm, first, second in arms:
        for label, only in (("all readers", None), ("not-blind readers", not_blind)):
            recs = valid_in(arm, only)
            picks, ties = picks_in(recs)
            versions = [first] if first == second else [first, second]
            out.append("reads %s %s: valid=%d %s tie=%d" % (
                label, arm, len(recs),
                " ".join("%s=%d" % (v, picks.get(v, 0)) for v in versions), ties))

    # A/A gate
    aa_planned = len([r for r in reads if r.arm == AA])
    aa_valid = valid_in(AA)
    if aa_planned == 0 or len(aa_valid) < aa_planned:
        gate = "not evaluated"
        out.append("A/A gate: not evaluated (%d valid reads of %d planned)"
                   % (len(aa_valid), aa_planned))
    else:
        strong = len([x for x in aa_valid
                      if x.reply.choice != "TIE" and x.reply.strength in STRONG])
        share = Fraction(strong, len(aa_valid))
        if share >= plan.noise_threshold:
            gate = "tripped"
            out.append("A/A gate: tripped (%d of %d valid A/A reads clearly or strongly "
                       "non-TIE, %s; threshold %s)" % (strong, len(aa_valid),
                                                     _percent(strong, len(aa_valid)),
                                                     plan.noise_threshold))
        else:
            gate = "passed"
            out.append("A/A gate: passed (%d of %d valid A/A reads clearly or strongly "
                       "non-TIE; threshold %s)" % (strong, len(aa_valid),
                                                 plan.noise_threshold))

    # position
    position = {}
    total_a = total_picks = 0
    for arm, _first, _second in arms:
        slots = [_pick(x)[1] for x in valid_in(arm)]
        slots = [s for s in slots if s is not None]
        in_a = len([s for s in slots if s == "A"])
        total_a += in_a
        total_picks += len(slots)
        if len(slots) < 2:
            position[arm] = "not assessable"
        elif in_a in (0, len(slots)):
            position[arm] = "INCONCLUSIVE"
        else:
            position[arm] = "no slot bias"
        share = "" if not slots else " (%s)" % _percent(in_a, len(slots))
        out.append("position %s: %d of %d non-TIE picks in slot A%s: %s"
                   % (arm, in_a, len(slots), share, position[arm]))
    if total_picks < 2:
        overall = "not assessable"
    elif total_a in (0, total_picks):
        overall = "INCONCLUSIVE"
    else:
        overall = "no slot bias"
    share = "" if not total_picks else " (%s)" % _percent(total_a, total_picks)
    out.append("position overall: %d of %d non-TIE picks in slot A%s: %s"
               % (total_a, total_picks, share, overall))

    # hypotheses
    for hyp in plan.hypotheses:
        arm = "c%d" % hyp.comparison
        recs = valid_in(arm)
        picks, ties = picks_in(recs)
        first, second = plan.comparisons[hyp.comparison - 1]
        rule = ["%s if %s" % (kind, clause.text()) for kind, clause in hyp.clauses]
        verdict = "INCONCLUSIVE"
        for kind, clause in hyp.clauses:
            if _clause_holds(clause, len(recs), picks):
                verdict = kind
                break
        reasons = []
        if gate == "tripped":
            verdict = "INCONCLUSIVE"
            reasons.append("the A/A gate tripped")
        elif gate == "not evaluated":
            verdict = "INCONCLUSIVE"
            reasons.append("the A/A gate was not evaluated")
        if position[arm] == "INCONCLUSIVE":
            verdict = "INCONCLUSIVE"
            reasons.append("position is INCONCLUSIVE on %s" % arm)
        out.append("hypothesis %s rule: %s" % (hyp.name, "; ".join(rule) or "none"))
        out.append("hypothesis %s counts: valid=%d %s=%d %s=%d tie=%d" % (
            hyp.name, len(recs), first, picks.get(first, 0), second,
            picks.get(second, 0), ties))
        out.append("hypothesis %s verdict: %s" % (hyp.name, verdict))
        for reason in reasons:
            out.append("hypothesis %s reason: %s" % (hyp.name, reason))

    # mechanisms
    def matching(recs, mech):
        count = 0
        for x in recs:
            for field in mech.fields:
                value = x.reply.rationale if field == "PREFER" else x.reply.fields.get(field, "")
                if re.search(mech.pattern, value, re.I):
                    count += 1
                    break
        return count

    for mech in plan.mechanisms:
        arm = "c%d" % mech.comparison
        label = "mechanism %s in %s" % (_show(mech.name), arm)
        recs = valid_in(arm)
        floor_recs = valid_in(AA)
        count, floor = matching(recs, mech), matching(floor_recs, mech)
        out.append("%s count: %d of %d valid reads" % (label, count, len(recs)))
        out.append("%s A/A floor: %d of %d valid reads" % (label, floor, len(floor_recs)))
        if recs and floor_recs and Fraction(count, len(recs)) > Fraction(floor, len(floor_recs)):
            out.append("%s separation: separates the versions from the A/A floor" % label)
            verdict = "SUPPORTED" if count >= mech.k else "INCONCLUSIVE"
        else:
            out.append("%s separation: unable to separate the versions" % label)
            verdict = "INCONCLUSIVE"
        reasons = []
        if gate == "tripped":
            verdict = "INCONCLUSIVE"
            reasons.append("the A/A gate tripped")
        elif gate == "not evaluated":
            verdict = "INCONCLUSIVE"
            reasons.append("the A/A gate was not evaluated")
        out.append("%s verdict: %s (SUPPORTED at %d or more)" % (label, verdict, mech.k))
        for reason in reasons:
            out.append("%s reason: %s" % (label, reason))

    # scores
    for arm, first, second in arms:
        recs = valid_in(arm)
        for version in ([first] if first == second else [first, second]):
            mine = []
            for x in recs:
                if x.read.slot_a == version:
                    mine.append((x.read.reader, x.reply.score_a))
                if x.read.slot_b == version:
                    mine.append((x.read.reader, x.reply.score_b))
            if mine:
                out.append("scores %s version %s: scores=%d total=%d mean=%s" % (
                    arm, version, len(mine), sum(s for _r, s in mine),
                    _mean(sum(s for _r, s in mine), len(mine))))
            for reader in plan.readers:
                by = [s for r, s in mine if r == reader.name]
                if by:
                    out.append("scores %s reader %s version %s: scores=%d total=%d mean=%s"
                               % (arm, reader.name, version, len(by), sum(by),
                                  _mean(sum(by), len(by))))
    aa_scores = []
    for x in valid_in(AA):
        aa_scores += [x.reply.score_a, x.reply.score_b]
    if aa_scores:
        out.append("A/A score spread: %d (highest %d, lowest %d)"
                   % (max(aa_scores) - min(aa_scores), max(aa_scores), min(aa_scores)))
    else:
        out.append("A/A score spread: none (no valid A/A read)")

    # spend, failed reads and the cut
    out.append("spend tally: %s (a tally of declared costs, not measured spend); ceiling: %s"
               % (_show(str(log.get("spend"))), _show(str(log.get("spend ceiling")))))
    failed = [x for x in records if x.status == "failed"]
    out.append("failed reads: %d" % len(failed))
    for x in failed:
        line = "failed read %s: %s" % (_show(x.read.id), _show(x.reason))
        out.append(line)
        problems.append(line)
    if cut:
        line = "cut: ran %s of %s planned reads at spend ceiling %s" % (
            _show(str(log.get("reads run"))), _show(str(log.get("planned reads"))),
            _show(str(log.get("spend ceiling"))))
        problems.append(line)
    else:
        line = "cut: no"
    out.append(line)
    if stopped is not None:
        line = "stopped: %s" % _show(stopped)
        out.append(line)
        problems.append(line)

    exit_code = 2 if stopped is not None else 1 if (failed or cut) else 0
    out.append("exit status: %d" % exit_code)
    text = "".join(line + "\n" for line in out)
    number = 1
    while True:
        path = os.path.join(folder, "%s%d.txt" % (RESULT_STEM, number))
        try:
            _write_new(folder, path, text, taken=True)
            break
        except FileExistsError:
            number += 1
    return Result(exit_code, True, text=text, error="\n".join(problems),
                  stopped=None if stopped is None else _show(stopped))
