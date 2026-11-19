"""Reader A/B harness: compare two versions of a career document by reader scores.

The behaviour is stated in docs/specs/reader-ab.md. In short: freeze a plan and its inputs by
hash, check the hashes and that the two versions differ only where the plan says, run the
A/A arm and then each comparison with readers, and score the replies against the frozen
rules. Every function that does work returns a Result, as the other tools do.

This module reads the plan file (``parse``), runs the built-in fake reader inside the tool,
and runs a live reader (a command the user names) only through ``ab_reader_command``. The
parts it shares with ``track-record panel`` (the plan-file syntax, the freeze, the run folder,
live reads and the result's tail) live in ``reader_harness``.
"""

import copy
import hashlib
import math
import os
import re
from fractions import Fraction

from career_track_record import reader_harness as harness
from career_track_record import series
from career_track_record import stats

# File names inside a read folder, and in the run folder. Every use goes through these.
READ_A = "A.txt"
READ_B = "B.txt"
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

# Everything printed that came from an argument, a file name or a file's contents goes through
# this one function (the one ``tone`` and ``barred`` print paths with), so that no value can
# split a line or hide in an invisible character.
_show = harness.show

Result = harness.Result
Reader = harness.Reader
PlanError = harness.PlanError
Unreadable = harness.Unreadable
RunFolderError = harness.RunFolderError
collapsed_lines = harness.collapsed_lines
changed_lines = harness.changed_lines
read_text = harness.read_text

AA = "aa"
SENS = "s"
LABELS = ("READ", "PRIOR", "SCORE-A", "SCORE-B", "PREFER", "DROVE-IT", "DOUBTS",
          "UNDERSOLD", "OVEREXPLAINED", "OWNED", "FLAG-FIXES")
FREE_TEXT_FIELDS = ("DROVE-IT", "DOUBTS", "UNDERSOLD", "OVEREXPLAINED", "OWNED",
                    "FLAG-FIXES", "PREFER")
STRENGTHS = ("slightly", "clearly", "strongly")
SLIGHTLY = "slightly"
# Each reader's reads of an arm come in pairs (its first and second, third and fourth, ...),
# so the count is even.
DEFAULT_READS_PER_READER = 6
# Who drafted a version, besides one or more model families (revision 4).
DRAFTERS = ("user", "third-party", "unknown")
MISSING_DRAFTED_BY = "a version needs drafted-by (revision 4): "
DRAFTED_BY_FORMS = ("drafted-by is user, third-party, unknown or model <family>, with more "
                    "models as a comma list: ")
MISSING_FAMILY = "a reader needs a family (revision 4): "
EARLIER_REVISION = ("frozen under an earlier revision: %s has no family on a reader or no "
                    "drafted-by on a version; score it with the release that froze it, or "
                    "rewrite it as a new plan")
# The family rule needs at least this many valid pairs from the other families.
FAMILY_MIN_PAIRS = 3

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

# The kinds of document a plan may name with ``document``. The reader prompt above is written
# for the first; the others change only the noun (and its article) wherever the prompt names
# the document.
RESUME = "résumé"
DOCUMENTS = (RESUME, "cover letter", "essay", "profile")
_DOCUMENT_PLACES = (("reading a résumé for", "reading %s for"),
                    ("one version of the résumé", "one version of the %s"),
                    ("another version of the same résumé", "another version of the same %s"))


def _with_article(document):
    return ("an " if document[0] in "aeiou" else "a ") + document


def render_prompt(document=RESUME):
    """The reader prompt for a kind of document. For the default it is ``PROMPT`` itself."""
    if document == RESUME:
        return PROMPT
    text = PROMPT
    for old, new in _DOCUMENT_PLACES:
        assert text.count(old) == 1, old
        text = text.replace(old, new % (_with_article(document) if "%s for" in new
                                        else document))
    return text


# ------------------------------------------------------------------ the plan model

class FakeRule(object):
    """One rule of the fake reader. Build one with the class methods below.

    ``arms`` names the arms it applies to ("aa", "s", "c1", "c2", ...); by default every
    comparison and neither the A/A arm nor the sensitivity arm. ``on_reads`` is a set of read numbers counted across
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
                 reads_per_reader=6, hypotheses=(), mechanisms=(), change_scope=(),
                 noise_threshold=Fraction(1, 2), spend_ceiling=None, aa_version=None,
                 amends=None, read_timeout=DEFAULT_READ_TIMEOUT, sidedness="two",
                 alpha=Fraction(1, 20), alpha_text="0.05", sensitivity=None,
                 sensitivity_scope=(), sensitivity_threshold=Fraction(5, 6), min_valid_reads=None,
                 replicate_of=None, document=RESUME, drafted_by=None, extends=None,
                 aa_pool=(), aa_band=False, series=None, series_note=None, series_line=None):
        self.posting = posting
        self.aa_band = aa_band
        # the series file (a path relative to the plan's folder), its note, and the plan line
        # that names it; None for a plan that names no series
        self.series = series
        self.series_note = series_note
        self.series_line = series_line
        self.extends = extends
        self.aa_pool = list(aa_pool)
        self.document = document
        # version name -> "user", "third-party", "unknown" or a tuple of model families
        self.drafted_by = dict(drafted_by or {})
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
        self.replicate_of = replicate_of
        self.read_timeout = read_timeout
        self.sidedness = sidedness
        self.alpha = alpha
        self.alpha_text = alpha_text
        self.sensitivity = sensitivity
        self.sensitivity_scope = list(sensitivity_scope)
        self.sensitivity_threshold = sensitivity_threshold
        self.min_valid_reads = min_valid_reads

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

_LIST_KEYS = ("versions", "comparisons", "readers", "hypotheses", "mechanisms",
              "change-scope", "sensitivity-scope", "fake-reader", "aa-pool")
_SCALAR_KEYS = ("posting", "aa-version", "reads-per-reader", "noise-threshold",
                "spend-ceiling", "amends", "replicate-of", "read-timeout", "sidedness", "alpha",
                "sensitivity", "sensitivity-threshold", "min-valid-reads", "document",
                "extends", "aa-band", "series", "series-note")
_NAME = harness.NAME
_INTEGER = harness.INTEGER
_FRACTION = re.compile(r"([0-9]+)/([0-9]+)\Z")
_COMPARISON = re.compile(r"(\S+) vs (\S+)\Z")
_CLAUSE = re.compile(r"(SUPPORTED|REFUTED) if (\S+) (?:is )?preferred in "
                     r"(?:([0-9]+) of ([0-9]+)|([0-9]+) or more)\Z")
_SUPPORTED_AT = re.compile(r"supported at ([0-9]+) or more\Z")
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

    # versions
    versions = []
    names = set()
    drafted_by = {}
    for number, item in lists.get("versions", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) < 2:
            state.bad(number, "a version is written: name | file")
        elif not _NAME.match(parts[0]):
            state.bad(number, "a name holds letters, digits and - only: %s" % _short(parts[0]))
        elif parts[0] in names:
            state.bad(number, "the version %s is named twice" % parts[0])
        else:
            names.add(parts[0])
            versions.append((parts[0], parts[1]))
            if len(parts) == 2:
                state.bad(number, MISSING_DRAFTED_BY + parts[0])
            elif len(parts) > 3:
                state.bad(number, DRAFTED_BY_FORMS + _short(parts[3]))
            else:
                who = _drafted_by(parts[2])
                if who is None:
                    cause = (" (a bar inside a field starts a new field)"
                             if len(parts[2].split()) == 1 else "")
                    state.bad(number, DRAFTED_BY_FORMS + _short(parts[2]) + cause)
                else:
                    drafted_by[parts[0]] = who

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
    reads_per_reader = DEFAULT_READS_PER_READER
    if "reads-per-reader" in scalars:
        number, value = scalars["reads-per-reader"]
        got = state.integer(number, "reads-per-reader", value, minimum=1)
        if got is not None and got % 2 == 1:
            state.bad(number, "reads-per-reader must be an even number, read in pairs "
                      "(revision 4)")
            got = None
        reads_per_reader = got if got is not None else DEFAULT_READS_PER_READER
    noise = Fraction(1, 2)
    if "noise-threshold" in scalars:
        number, value = scalars["noise-threshold"]
        match = _FRACTION.match(value)
        if not match or int(match.group(2)) == 0:
            state.bad(number, "noise-threshold is written as a fraction n/d")
        else:
            noise = Fraction(int(match.group(1)), int(match.group(2)))
    sidedness = "two"
    if "sidedness" in scalars:
        number, value = scalars["sidedness"]
        if value in ("two", "greater", "less"):
            sidedness = value
        else:
            state.bad(number, "sidedness is two, greater or less")
    alpha = Fraction(1, 20)
    alpha_text = "0.05"
    if "alpha" in scalars:
        number, value = scalars["alpha"]
        if re.fullmatch(r"0\.[0-9]+", value) and value.strip("0.") != "":
            alpha = Fraction(value)
            alpha_text = value
        else:
            state.bad(number, "alpha is written as 0. followed by digits, not all zero")
    sensitivity = None
    if "sensitivity" in scalars:
        number, value = scalars["sensitivity"]
        match = _COMPARISON.match(value)
        if not match:
            state.bad(number, "sensitivity is written: X vs W")
        elif match.group(1) not in names or match.group(2) not in names:
            state.bad(number, "the sensitivity pair names a version the plan does not have")
        else:
            sensitivity = (match.group(1), match.group(2))
    sensitivity_threshold = Fraction(5, 6)
    if "sensitivity-threshold" in scalars:
        number, value = scalars["sensitivity-threshold"]
        match = _FRACTION.match(value)
        if not match or int(match.group(2)) == 0:
            state.bad(number, "sensitivity-threshold is written as a fraction n/d")
        else:
            got = Fraction(int(match.group(1)), int(match.group(2)))
            if got <= Fraction(1, 2) or got > 1:
                state.bad(number, "sensitivity-threshold must be above 1/2 and at most 1")
            else:
                sensitivity_threshold = got
    document = RESUME
    if "document" in scalars:
        number, value = scalars["document"]
        if value in DOCUMENTS:
            document = value
        else:
            state.bad(number, "document is résumé, cover letter, essay or profile")
    aa_band = False
    if "aa-band" in scalars:
        number, value = scalars["aa-band"]
        if value == "on":
            aa_band = True
        else:
            state.bad(number, "aa-band is on, or the line is left out: %s" % _short(value))
    series_path = series_note = series_line = None
    if "series" in scalars:
        series_line, series_path = scalars["series"]
        if len(comparisons) > 1:
            state.bad(series_line, "a plan with series has exactly one comparison")
    if "series-note" in scalars:
        number, series_note = scalars["series-note"]
        if "series" not in scalars:
            state.bad(number, "series-note is set but the plan names no series file; add a "
                              "series line, or remove series-note")
        if "\t" in series_note:
            state.bad(number, "series-note holds a tab")
    min_valid_reads = None
    if "min-valid-reads" in scalars:
        number, value = scalars["min-valid-reads"]
        min_valid_reads = state.integer(number, "min-valid-reads", value, minimum=1)
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

    extends = None
    if "extends" in scalars:
        number, extends = scalars["extends"]
        if not extends.endswith(harness.FREEZE_SUFFIX):
            state.bad(number, "extends must name a .freeze file")
        if "amends" in scalars or "replicate-of" in scalars or lists.get("aa-pool"):
            state.bad(number, "a plan may not carry extends with amends, replicate-of or "
                      "aa-pool")
    aa_pool = []
    for number, item in lists.get("aa-pool", []):
        if not item.endswith(harness.FREEZE_SUFFIX):
            state.bad(number, "aa-pool names .freeze files: %s" % _short(item))
        elif item in aa_pool:
            state.bad(number, "aa-pool names %s twice" % _short(item))
        else:
            aa_pool.append(item)

    # readers, each with its model family (revision 4)
    readers = harness.parse_readers(state, lists.get("readers", []), family=True)
    without = set(r.name for r in readers if r.family is None)
    for number, item in lists.get("readers", []):
        name = item.split("|")[0].strip()
        if name in without:
            without.discard(name)
            state.bad(number, MISSING_FAMILY + name)

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
        clauses = _hypothesis_clauses(state, number, rest[0], comparisons[comparison - 1],
                                      sensitivity)
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

    # sensitivity scope
    sensitivity_scope = []
    for number, item in lists.get("sensitivity-scope", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) != 1:
            state.bad(number, "a sensitivity-scope item is a pattern")
        elif state.pattern(number, parts[0]):
            if re.fullmatch(parts[0], "") or re.search(parts[0], ""):
                state.bad(number, "a sensitivity-scope pattern must not match empty text")
            else:
                sensitivity_scope.append(parts[0])
    if "sensitivity" in scalars and not lists.get("sensitivity-scope"):
        state.bad(scalars["sensitivity"][0], "a sensitivity pair needs a sensitivity-scope")
    if "sensitivity-scope" in lists and "sensitivity" not in scalars:
        for number, raw in enumerate(harness.LINE_BREAK.split(text), 1):
            if raw[:1] not in " \t" and raw.partition(":")[0].strip() == "sensitivity-scope":
                state.bad(number, "sensitivity-scope needs a sensitivity pair")
                break

    # the fake reader
    has_fake = any(r.kind == "fake" for r in readers)
    reads = len(readers) * reads_per_reader
    rules, rule_lines = [], []
    for number, item in lists.get("fake-reader", []):
        rule = _fake_rule(state, number, item, comparison_text, reads,
                          "sensitivity" in scalars)
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
    if series_path is not None and not lists.get("hypotheses"):
        state.problems.append("the plan names a series file but no hypothesis; add a "
                              "hypothesis, or remove the series line")
    if state.problems:
        raise PlanError(state.problems)
    return Plan(posting, versions, comparisons, readers, fake_rules=rules,
                reads_per_reader=reads_per_reader, hypotheses=hypotheses,
                mechanisms=mechanisms, change_scope=change_scope, noise_threshold=noise,
                spend_ceiling=ceiling, aa_version=aa_version, amends=amends,
                read_timeout=timeout, sidedness=sidedness, alpha=alpha,
                alpha_text=alpha_text, sensitivity=sensitivity,
                sensitivity_scope=sensitivity_scope,
                sensitivity_threshold=sensitivity_threshold,
                min_valid_reads=min_valid_reads, replicate_of=replicate_of,
                document=document, drafted_by=drafted_by, extends=extends, aa_pool=aa_pool,
                aa_band=aa_band, series=series_path, series_note=series_note,
                series_line=series_line)


def _drafted_by(text):
    """Who drafted a version, from its ``drafted-by <who>`` field: ``user``, ``third-party``,
    ``unknown``, or the tuple of model families (lower-cased, each once, in order). None when
    the field is in none of the four forms."""
    if not text.startswith("drafted-by "):
        return None
    who = text[len("drafted-by "):].strip()
    if who in DRAFTERS:
        return who
    families = []
    for piece in who.split(", "):
        match = re.match(r"model ([A-Za-z0-9-]+)\Z", piece)
        if not match:
            return None
        if match.group(1).lower() not in families:
            families.append(match.group(1).lower())
    return tuple(families)


def _hypothesis_clauses(state, number, rule, pair, sensitivity=None):
    """The ordered (verdict, Clause) list of a hypothesis rule, or None. A clause may not
    name the weakened copy of the sensitivity pair."""
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
        if sensitivity is not None and version == sensitivity[1]:
            state.bad(number, "a hypothesis may not name the weakened copy of the sensitivity "
                      "pair: %s" % _short(version))
            ok = False
            continue
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


def _fake_rule(state, number, item, comparison_text, reads, has_pair=False):
    """One FakeRule from a fake-reader item, or None with a problem recorded."""
    parts = state.fields(number, item)
    if parts is None:
        return None
    arms = None
    if len(parts) > 1 and (parts[0] in ("all", AA, SENS) or parts[0] in comparison_text):
        if parts[0] == SENS and not has_pair:
            state.bad(number, "an s rule needs a sensitivity pair")
            return None
        if parts[0] == AA:
            arms = [AA]
        elif parts[0] == SENS:
            arms = [SENS]
        elif parts[0] != "all":
            arms = ["c%d" % (comparison_text.index(parts[0]) + 1)]
        parts = parts[1:]
    rule_text, extras = parts[0], parts[1:]
    strength, on_read, ok = harness.rule_extras(state, number, extras, reads, STRENGTHS)
    if not ok:
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
        with harness.unlimited_int_digits():
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

def prompt_sha256(document=RESUME):
    return hashlib.sha256(render_prompt(document).encode("utf-8")).hexdigest()


def _plan_prompt_sha256(plan_path):
    """The prompt hash for the document the plan names; the default when the plan cannot be
    read (the caller then reports the plan's problems)."""
    try:
        return prompt_sha256(parse(plan_path).document)
    except (PlanError, OSError):
        return prompt_sha256()


def _inputs(plan, plan_path):
    """Ordered (label, absolute path) of the plan file and every input it names."""
    folder = harness.folder_of(plan_path)
    items = [(os.path.basename(plan_path), os.path.abspath(plan_path)),
             (plan.posting, os.path.join(folder, plan.posting))]
    for _name, path in plan.versions:
        items.append((path, os.path.join(folder, path)))
    if plan.amends is not None:
        items.append((plan.amends, os.path.join(folder, plan.amends)))
    if plan.replicate_of is not None:
        items.append((plan.replicate_of, os.path.join(folder, plan.replicate_of)))
    if plan.extends is not None:
        items.append((plan.extends, os.path.join(folder, plan.extends)))
    for item in plan.aa_pool:
        items.append((item, os.path.join(folder, item)))
    return harness.unique_inputs(items)


# ------------------------------------------------------------------ amendments, extensions, pools

SETTINGS = (("noise-threshold", "noise_threshold"), ("sensitivity-threshold",
                                                     "sensitivity_threshold"),
            ("alpha", "alpha"), ("min-valid-reads", "min_valid_reads"),
            ("aa-band", "aa_band"))
AMEND_RULE = ("an amendment may restate a rule's counts at the same share, and change nothing "
              "else: ")
EXTEND_ONLY = ("an extension may change only reads-per-reader and the number of readers of "
               "each model: ")
SAMPLE_SIZE_KEYS = ("reads-per-reader", "readers", "extends")


def blind_readers(plan):
    return [r for r in plan.readers if not r.not_blind]


def planned_pairs(plan):
    """The pairs one comparison arm plans for the plan's blind readers."""
    return len(blind_readers(plan)) * plan.reads_per_reader // 2


def planned_blind_reads(plan):
    return len(blind_readers(plan)) * plan.reads_per_reader


def _scaled(count, old, new):
    """``count`` over ``old`` planned units, restated over ``new``, as an exact fraction; None
    when there is no share to restate."""
    return Fraction(count * new, old) if old else None


def _is_whole(value):
    return value is not None and value.denominator == 1


def _read_plan(path):
    try:
        return parse(path)
    except (PlanError, OSError, Unreadable, RunFolderError, UnicodeDecodeError):
        return None


def _freeze_entries(folder, named):
    """(freeze path, recorded hashes by label, or None) of the freeze file ``named`` relative
    to ``folder``."""
    freeze_path = os.path.join(folder, named)
    if not os.path.isfile(freeze_path):
        return freeze_path, None
    try:
        return freeze_path, dict(harness.read_freeze(freeze_path))
    except (OSError, UnicodeDecodeError):
        return freeze_path, None


def amendment_problems(plan_path, plan):
    """The problems of an amendment against the plan it amends, in order; none when the plan
    amends nothing or the amended freeze is not there (the freeze reports it missing). An
    amendment may change the read count, never a threshold: each count rule keeps its share
    over the arm's planned pairs (a mechanism's, over its planned reads), and the four
    threshold settings and ``aa-band`` are as the amended plan has them."""
    if plan.amends is None or not plan.amends.endswith(harness.FREEZE_SUFFIX):
        return []
    folder = harness.folder_of(plan_path)
    freeze_path, recorded = _freeze_entries(folder, plan.amends)
    if not os.path.isfile(freeze_path):
        return []
    if recorded is None:
        return ["cannot read the freeze file: %s" % _show(plan.amends)]
    named = plan.amends[:-len(harness.FREEZE_SUFFIX)]
    old_path = freeze_path[:-len(harness.FREEZE_SUFFIX)]
    if not os.path.isfile(old_path):
        return ["the amended plan is missing: %s" % _show(named)]
    if recorded.get(os.path.basename(old_path)) != harness.sha256_file(old_path):
        return ["changed since the freeze: %s" % _show(named)]
    old = _read_plan(old_path)
    if old is None:
        return ["the amended plan cannot be read under revision 4: %s" % _show(named)]
    problems = []
    for setting, attribute in SETTINGS:
        if getattr(old, attribute) != getattr(plan, attribute):
            problems.append("an amendment may not change %s from the plan it amends" % setting)
    pairs_old, pairs_new = planned_pairs(old), planned_pairs(plan)
    reads_old, reads_new = planned_blind_reads(old), planned_blind_reads(plan)

    def same_share(count_old, count_new, total_old, total_new):
        need = _scaled(count_old, total_old, total_new)
        if not _is_whole(need):
            return False
        return need == count_new

    for index in range(max(len(old.hypotheses), len(plan.hypotheses))):
        if index >= len(old.hypotheses) or index >= len(plan.hypotheses):
            problems.append(AMEND_RULE + "h%d" % (index + 1))
            continue
        a, b = old.hypotheses[index], plan.hypotheses[index]
        ok = a.comparison == b.comparison and len(a.clauses) == len(b.clauses)
        for (kind_a, clause_a), (kind_b, clause_b) in zip(a.clauses, b.clauses):
            ok = ok and kind_a == kind_b and clause_a.version == clause_b.version
            ok = ok and (clause_a.n is None) == (clause_b.n is None)
            ok = ok and same_share(clause_a.k, clause_b.k, pairs_old, pairs_new)
            if clause_a.n is not None and clause_b.n is not None:
                ok = ok and same_share(clause_a.n, clause_b.n, pairs_old, pairs_new)
        if not ok:
            problems.append(AMEND_RULE + b.name)
    for index in range(max(len(old.mechanisms), len(plan.mechanisms))):
        if index >= len(old.mechanisms) or index >= len(plan.mechanisms):
            longer = old.mechanisms if index < len(old.mechanisms) else plan.mechanisms
            problems.append(AMEND_RULE + _show(longer[index].name))
            continue
        a, b = old.mechanisms[index], plan.mechanisms[index]
        if not (a.name == b.name and a.comparison == b.comparison and a.fields == b.fields
                and same_share(a.k, b.k, reads_old, reads_new)):
            problems.append(AMEND_RULE + _show(b.name))
    return problems


def _models(plan):
    return [(r.command, r.family, r.not_blind, r.cost, r.group) for r in plan.readers]


def _structure_of(path):
    state = harness.ParseState()
    return harness.structure(state, harness.plan_text(path), _LIST_KEYS, _SCALAR_KEYS)


def _scaled_rules(plan, first):
    """(hypotheses, mechanisms, problems) of an extension's rules read at the pooled pairs:
    each count follows the pooled planned pairs (a mechanism's, the pooled planned reads), and
    a count that is not whole is a problem naming the rule."""
    pairs_first = planned_pairs(first)
    pooled = pairs_first + planned_pairs(plan)
    reads_first = planned_blind_reads(first)
    pooled_reads = reads_first + planned_blind_reads(plan)
    problems, hypotheses, mechanisms = [], [], []
    for hyp in plan.hypotheses:
        clauses, ok = [], True
        for kind, clause in hyp.clauses:
            k = _scaled(clause.k, pairs_first, pooled)
            n = None if clause.n is None else _scaled(clause.n, pairs_first, pooled)
            if not _is_whole(k) or (clause.n is not None and not _is_whole(n)):
                ok = False
                break
            clauses.append((kind, Clause(clause.version, int(k), None if n is None else int(n))))
        if ok:
            hypotheses.append(Hypothesis(hyp.name, hyp.comparison, clauses))
        else:
            problems.append("an extension's pooled pairs give no whole number for %s" % hyp.name)
            hypotheses.append(hyp)
    for mech in plan.mechanisms:
        k = _scaled(mech.k, reads_first, pooled_reads)
        if _is_whole(k):
            mechanisms.append(Mechanism(mech.name, mech.comparison, mech.pattern, int(k),
                                        mech.fields))
        else:
            problems.append("an extension's pooled pairs give no whole number for %s"
                            % _show(mech.name))
            mechanisms.append(mech)
    return hypotheses, mechanisms, problems


def extension_problems(plan_path, plan):
    """The problems of an extension against its first run, in order. An extension may change
    the sample size only."""
    if plan.extends is None or not plan.extends.endswith(harness.FREEZE_SUFFIX):
        return []
    folder = harness.folder_of(plan_path)
    freeze_path, recorded = _freeze_entries(folder, plan.extends)
    if not os.path.isfile(freeze_path):
        return []
    if recorded is None:
        return ["cannot read the freeze file: %s" % _show(plan.extends)]
    named = plan.extends[:-len(harness.FREEZE_SUFFIX)]
    first_path = freeze_path[:-len(harness.FREEZE_SUFFIX)]
    if not os.path.isfile(first_path):
        return ["the first plan is missing: %s" % _show(named)]
    if recorded.get(os.path.basename(first_path)) != harness.sha256_file(first_path):
        return ["changed since the freeze: %s" % _show(named)]
    first = _read_plan(first_path)
    if first is None:
        return ["the first plan cannot be read under revision 4: %s" % _show(named)]
    if first.extends is not None or first.amends is not None or first.replicate_of is not None:
        return ["extends must name a first run, not an amendment, a replicate or an extension: "
                "%s" % _show(named)]
    problems = []
    mine_scalars, mine_lists = _structure_of(plan_path)
    first_scalars, first_lists = _structure_of(first_path)
    for key in sorted(set(mine_scalars) | set(first_scalars) | set(mine_lists)
                      | set(first_lists)):
        if key in SAMPLE_SIZE_KEYS:
            continue
        mine = (mine_scalars[key][1] if key in mine_scalars
                else [x for _n, x in mine_lists.get(key, [])] if key in mine_lists else None)
        theirs = (first_scalars[key][1] if key in first_scalars
                  else [x for _n, x in first_lists.get(key, [])] if key in first_lists else None)
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
    if recorded.get(PROMPT_LABEL) != prompt_sha256(plan.document):
        problems.append("changed since the first freeze: %s" % PROMPT_LABEL)
    problems += _scaled_rules(plan, first)[2]
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
            files = [n for n in os.listdir(other) if n.endswith(harness.FREEZE_SUFFIX)]
        except OSError:
            continue
        for file_name in sorted(files):
            their = _read_plan(os.path.join(other, file_name[:-len(harness.FREEZE_SUFFIX)]))
            if (their is not None and their.extends is not None
                    and os.path.realpath(os.path.join(other, their.extends))
                    == os.path.realpath(freeze_path)):
                problems.append("the first run already has an extension: %s" % _show(name))
    return problems


def pool_problems(plan_path, plan):
    """The problems of each ``aa-pool`` item, in order. A pooled run must share with this one,
    by hash, the prompt, the reader commands, the A/A version file and the posting."""
    folder = harness.folder_of(plan_path)
    problems = []
    for item in plan.aa_pool:
        freeze_path, recorded = _freeze_entries(folder, item)
        if not os.path.isfile(freeze_path):
            continue
        if os.path.realpath(os.path.dirname(freeze_path)) == os.path.realpath(folder):
            problems.append("aa-pool names a run in this folder: %s" % _show(item))
            continue
        if recorded is None:
            problems.append("cannot read the freeze file: %s" % _show(item))
            continue
        named = item[:-len(harness.FREEZE_SUFFIX)]
        pooled_path = freeze_path[:-len(harness.FREEZE_SUFFIX)]
        if not os.path.isfile(pooled_path):
            problems.append("the pooled plan is missing: %s" % _show(named))
            continue
        if recorded.get(os.path.basename(pooled_path)) != harness.sha256_file(pooled_path):
            problems.append("changed since the freeze: %s" % _show(named))
            continue
        pooled = _read_plan(pooled_path)
        if pooled is None:
            problems.append("the pooled plan cannot be read under revision 4: %s"
                            % _show(named))
            continue
        mine_aa = plan.version_path(plan.effective_aa_version())
        mine_aa_hash = harness.sha256_file(os.path.join(folder, mine_aa))
        pooled_aa = pooled.version_path(pooled.effective_aa_version())
        posting_path = os.path.join(folder, plan.posting)
        differs = []
        if recorded.get(PROMPT_LABEL) != prompt_sha256(plan.document):
            differs.append("the prompt")
        if [r.command for r in pooled.readers] != [r.command for r in plan.readers]:
            differs.append("the reader commands")
        if not os.path.isfile(os.path.join(folder, mine_aa)) or \
                recorded.get(pooled_aa) != mine_aa_hash:
            differs.append("the A/A version file")
        if not os.path.isfile(posting_path) or \
                recorded.get(pooled.posting) != harness.sha256_file(posting_path):
            differs.append("the posting")
        for what in differs:
            problems.append("the pooled run differs in %s: %s" % (what, _show(item)))
    return problems


def _refused_by_series(plan, plan_path, sub, environ):
    """A Result for a refusal of the series write by the record folder (series.refusal), or
    None. The line is the one to print as written, whatever its exit code (1 or 2)."""
    found = series.refusal(plan, plan_path, sub, environ)
    if found is None:
        return None
    code, line = found
    return Result(code, False, error=line, refusal=line)


def freeze(plan_path, now=None, environ=None):
    """Read the plan, hash it and every input it names, and write the freeze file beside it.
    Every plan problem is found here, an amendment's, an extension's, a pool's and a series
    file's included. ``now`` is the clock the series checks read (a datetime; the real UTC time
    by default); the command line has no way to set it. ``environ`` is what the record-folder
    check of the series file reads the config from (None: this process's environment)."""
    plan = _read_plan(plan_path)
    if plan is not None:
        refused = _refused_by_series(plan, plan_path, "freeze", environ)
        if refused is not None:
            return refused
        problems = (amendment_problems(plan_path, plan) + extension_problems(plan_path, plan)
                    + pool_problems(plan_path, plan)
                    + series.plan_problems(plan, plan_path, now))
        if problems:
            return Result(2, False, error="\n".join(problems))
    return harness.freeze(plan_path, parse, _inputs, _plan_prompt_sha256(plan_path))


def _parse_frozen(path):
    """``parse`` for ``run`` and ``score``: a frozen plan with no family on a reader or no
    drafted-by on a version was frozen under an earlier revision, and that is the one problem
    reported. It is never scored under revision 4's rules."""
    try:
        return parse(path)
    except PlanError as exc:
        earlier = [p for p in exc.problems
                   if p.partition(": ")[2].startswith((MISSING_FAMILY, MISSING_DRAFTED_BY))]
        if earlier:
            raise PlanError([EARLIER_REVISION % _show(os.path.basename(path))])
        raise


def _verify(plan_path, with_prompt):
    return harness.verify(plan_path, _parse_frozen, _inputs, _plan_prompt_sha256(plan_path),
                          with_prompt)


# ------------------------------------------------------------------ the isolation check

def _arms(plan):
    """(arm id, first version, second version): the A/A arm, the sensitivity arm when the
    plan has a pair, then each comparison."""
    aa = plan.effective_aa_version()
    arms = [(AA, aa, aa)]
    if plan.sensitivity is not None:
        arms.append((SENS, plan.sensitivity[0], plan.sensitivity[1]))
    for index, (first, second) in enumerate(plan.comparisons, 1):
        arms.append(("c%d" % index, first, second))
    return arms


def _isolation_problems(plan, plan_path):
    folder = harness.folder_of(plan_path)
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

    for arm, first, second in _arms(plan):
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
        if arm == SENS:
            scope, what = plan.sensitivity_scope, "sensitivity"
        else:
            index = int(arm[1:])
            scope = [pattern for comparison, pattern in plan.change_scope
                     if comparison in (None, index)]
            what = "change"
        for mark, line in changes:
            if not any(re.search(pattern, line) for pattern in scope):
                problems.append("%s: changed line outside the %s scope: %s %s"
                                % (arm, what, mark, _show(line)))
    return problems


# ------------------------------------------------------------------ reply format

_PREFER_PICK = re.compile(r"(A|B)\s*,\s*(slightly|clearly|strongly)(?![A-Za-z0-9])(.*)\Z",
                          re.S)
_PREFER_TIE = re.compile(r"TIE(?![A-Za-z0-9])(.*)\Z", re.S)
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


def parse_reply(text):
    """Parse a reply. A field starts a line as ``FIELD: value`` (case-sensitive) and runs to
    the next line that starts with a field name; text before the first field is ignored."""
    reply = Reply()
    fields, first_lines, repeated = harness.split_fields(text, LABELS)
    reply.fields = fields
    reply.prior_flag = harness.prior_flag(fields)
    if repeated:
        reply.failure = "%s appears twice" % repeated[0]
        return reply
    for label in ("READ", "SCORE-A", "SCORE-B", "PREFER"):
        if label not in fields:
            reply.failure = "missing %s" % label
            return reply
    reply.read_id = fields["READ"]
    with harness.unlimited_int_digits():
        reply.score_a = harness.whole_number(fields["SCORE-A"])
        reply.score_b = harness.whole_number(fields["SCORE-B"])
    if reply.score_a is None:
        reply.failure = "SCORE-A is not an integer"
    elif reply.score_b is None:
        reply.failure = "SCORE-B is not an integer"
    else:
        picked = _parse_prefer(first_lines["PREFER"])
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
            # The first read of each of the reader's pairs has the first-listed version in
            # slot A, the second read the second-listed one (counted within the reader).
            for own in range(plan.reads_per_reader):
                number += 1
                a, b = (first, second) if own % 2 == 0 else (second, first)
                reads.append(PlannedRead(arm, number, reader.name, a, b))
    return reads


def _applies(rule, read):
    if rule.arms is None:
        return read.arm not in (AA, SENS)
    return read.arm in rule.arms


def _fires(rule, read):
    return _applies(rule, read) and (rule.on_reads is None or read.number in rule.on_reads)


def random_pick(seed, arm, number, non_tie=False):
    """What a seeded random rule picks for read ``number`` of ``arm``: the first byte of the
    sha256 of "<seed>:<arm>:<number>". With ``non_tie`` an even byte is A and an odd byte
    is B. Without it the byte mod 3 is 0 for A, 1 for B and 2 for TIE."""
    with harness.unlimited_int_digits():
        text = "%s:%s:%d" % (seed, arm, number)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
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
    with harness.unlimited_int_digits():
        score_a, score_b = str(scores[0]), str(scores[1])
    values = {"READ": read.id, "PRIOR": "nothing", "SCORE-A": score_a, "SCORE-B": score_b}
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

def run(plan_path, live=False, now=None, environ=None):
    """Check, key, read and score. Writes the key, the reads, the run log and a result.
    ``now`` and ``environ`` are the clock and the environment of ``freeze``."""
    try:
        return _run(plan_path, live, now, environ)
    except RunFolderError as exc:
        return Result(2, False, error=exc.line)


def _first_folder(plan_path, plan):
    """The folder of the first run, as the plan's replicate-of text names it, or None."""
    if plan.replicate_of is None:
        return None
    return os.path.dirname(os.path.join(harness.folder_of(plan_path), plan.replicate_of))


def _first_run_problems(plan_path, plan):
    """A replicate, an extension and a run that pools A/A reads wait for the runs they read:
    each such folder must already hold a key."""
    folder = harness.folder_of(plan_path)
    problems = []
    first = _first_folder(plan_path, plan)
    if first is not None and not os.path.isfile(os.path.join(first, KEY_FILE)):
        problems.append("the first run has not been run yet: %s"
                        % _show(os.path.dirname(plan.replicate_of)))
    if plan.extends is not None and not os.path.isfile(
            os.path.join(os.path.dirname(os.path.join(folder, plan.extends)), KEY_FILE)):
        problems.append("the first run has not been run yet: %s"
                        % _show(os.path.dirname(plan.extends)))
    for item in plan.aa_pool:
        if not os.path.isfile(os.path.join(os.path.dirname(os.path.join(folder, item)),
                                           KEY_FILE)):
            problems.append("the pooled run has not been run yet: %s"
                            % _show(os.path.dirname(item)))
    return problems


def _run(plan_path, live, now=None, environ=None):
    folder = harness.folder_of(plan_path)
    plan, problems, recorded, freeze_hash = _verify(plan_path, with_prompt=True)
    if plan is not None:
        refused = _refused_by_series(plan, plan_path, "run", environ)
        if refused is not None:
            return refused
    if plan is not None:
        problems += _isolation_problems(plan, plan_path)
        posting = os.path.join(folder, plan.posting)
        if os.path.isfile(posting):
            try:
                read_text(posting)
            except Unreadable as exc:
                problems.append("cannot read %s: %s" % (_show(plan.posting), exc))
    problems += harness.run_folder_problems(folder)
    if plan is not None:
        problems += _first_run_problems(plan_path, plan)
        problems += series.plan_problems(plan, plan_path, now, recorded)
    if problems:
        return Result(2, False, error="\n".join(problems))
    planned = _planned_reads(plan)
    if plan.live_readers() and not live:
        return Result(0, True, text=harness.live_preview(plan.readers, plan.spend_ceiling,
                                                         planned))
    texts = dict((name, harness.text_of(folder, path)) for name, path in plan.versions)
    posting_text = harness.text_of(folder, plan.posting)
    key_text = "".join("%s\t%s\t%s\t%s\n" % (r.id, r.reader, r.slot_a, r.slot_b)
                       for r in planned)

    prompt_text = render_prompt(plan.document)

    def prepare(where, read):
        harness.write_new(folder, os.path.join(where, READ_A), texts[read.slot_a])
        harness.write_new(folder, os.path.join(where, READ_B), texts[read.slot_b])
        harness.write_new(folder, os.path.join(where, READ_POSTING), posting_text)
        harness.write_new(folder, os.path.join(where, READ_PROMPT), prompt_text)

    def reply_of(read):
        return fake_reply(read, plan.fake_rules, texts[read.slot_a], texts[read.slot_b])

    stopped = harness.run_reads(folder, planned, plan.readers, plan.spend_ceiling,
                                plan.read_timeout, key_text, prepare, reply_of)
    return harness.scored_after_run(
        stopped, lambda: _score_and_write(plan_path, plan, recorded, freeze_hash, now, environ))


def score(plan_path, now=None, environ=None):
    """Score the replies in the run folder again, against the frozen plan. Writes a new result."""
    def write(plan, recorded, freeze_hash):
        refused = _refused_by_series(plan, plan_path, "score", environ)
        if refused is not None:
            return refused
        problems = (_first_run_problems(plan_path, plan)
                    + series.plan_problems(plan, plan_path, now, recorded))
        if problems:
            return Result(2, False, error="\n".join(problems))
        return _score_and_write(plan_path, plan, recorded, freeze_hash, now, environ)

    return harness.score(plan_path, _parse_frozen, _inputs, _plan_prompt_sha256(plan_path), 4,
                         write)


# ------------------------------------------------------------------ scoring

def _pick(rec):
    """(version picked or None, slot picked or None) for a valid read."""
    choice = rec.reply.choice
    if choice == "A":
        return rec.read.slot_a, "A"
    if choice == "B":
        return rec.read.slot_b, "B"
    return None, None


_percent = harness.percent
_mean = harness.mean


VALIDITY_LINE = harness.VALIDITY_LINE

SIDE_TEXT = {"two": "two-sided", "greater": "one-sided greater", "less": "one-sided less"}


class Pair(object):
    """The two reads of one reader's pair in one arm, as score records (``second`` is None
    only for a key that gives the reader an odd number of reads). The pair is valid when
    both reads are valid, half-read when one is, and missing when neither is."""

    def __init__(self, arm, reader, first, second):
        self.arm = arm
        self.reader = reader
        self.first = first
        self.second = second

    def records(self):
        return [x for x in (self.first, self.second) if x is not None]

    def valid_records(self):
        return [x for x in self.records() if x.status == "valid"]

    @property
    def status(self):
        valid = len(self.valid_records())
        if valid == 2:
            return "valid"
        return "half" if valid == 1 else "missing"


def pairs_of(records):
    """The pairs of a list of score records: within each arm, each reader's reads in read
    number order pair as first and second, third and fourth, and so on. Pairs are formed
    within one list only, so pairs from two runs are never mixed."""
    grouped, order = {}, []
    for rec in records:
        key = (rec.read.arm, rec.read.reader)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(rec)
    pairs = []
    for key in order:
        mine = sorted(grouped[key], key=lambda x: x.read.number)
        for index in range(0, len(mine), 2):
            second = mine[index + 1] if index + 1 < len(mine) else None
            pairs.append(Pair(key[0], key[1], mine[index], second))
    return pairs


def read_version(rec, slightly_tie=False):
    """The version a valid read picks, or None for a TIE. With ``slightly_tie`` a
    ``slightly`` pick counts as a TIE (the second reading)."""
    if rec.reply.choice == "TIE":
        return None
    if slightly_tie and rec.reply.strength == SLIGHTLY:
        return None
    return _pick(rec)[0]


def pair_pick(pair, slightly_tie=False):
    """The version a valid pair picks, or None for a TIE pair: a pick counts only when both
    reads pick the same version, at any strength."""
    first = read_version(pair.first, slightly_tie)
    second = read_version(pair.second, slightly_tie)
    return first if first is not None and first == second else None


def pair_counts(pairs, slightly_tie=False):
    """(valid pairs, picks by version, TIE pairs) over the valid pairs in ``pairs``."""
    valid = [p for p in pairs if p.status == "valid"]
    picks, ties = {}, 0
    for p in valid:
        version = pair_pick(p, slightly_tie)
        if version is None:
            ties += 1
        else:
            picks[version] = picks.get(version, 0) + 1
    return len(valid), picks, ties


def _clause_holds(clause, valid, picks):
    """``<n> of <m>`` holds when exactly ``<m>`` pairs are valid and at least ``<n>`` pick the
    version; ``<n> or more`` when at least ``<n>`` do."""
    if clause is None:
        return False
    if clause.n is None:
        return picks.get(clause.version, 0) >= clause.k
    return valid == clause.n and picks.get(clause.version, 0) >= clause.k


def rule_verdict(hyp, valid, picks):
    """(verdict, deciding clause or None) of a hypothesis's frozen rule alone."""
    for kind, clause in hyp.clauses:
        if _clause_holds(clause, valid, picks):
            return kind, clause
    return "INCONCLUSIVE", None


def completion_outcomes(plan, hyp, pairs, first, second):
    """(possible verdicts, exact p-values, missing pairs) of the rule alone over every
    completion of the arm's pairs that are not valid. A missing pair completes as a pick for
    either version or a TIE; a half-read pair only as its valid read allows (a pick for the
    version that read picks, or a TIE; a TIE read only as a TIE). Each completion counts every
    pair in ``pairs`` as valid. No gate, position, floor or family rule is applied."""
    _valid, picks, _ties = pair_counts(pairs)
    x0, y0 = picks.get(first, 0), picks.get(second, 0)
    whole = half_x = half_y = half_t = 0
    for p in pairs:
        if p.status == "missing":
            whole += 1
        elif p.status == "half":
            version = read_version(p.valid_records()[0])
            if version == first:
                half_x += 1
            elif version == second:
                half_y += 1
            else:
                half_t += 1
    verdicts, exact = set(), []
    for x in range(whole + 1):
        for y in range(whole + 1 - x):
            for i in range(half_x + 1):
                for j in range(half_y + 1):
                    counts = {first: x0 + x + i, second: y0 + y + j}
                    verdicts.add(rule_verdict(hyp, len(pairs), counts)[0])
                    n = counts[first] + counts[second]
                    if n >= 1:
                        exact.append(stats.binomial_p(counts[second], n, plan.sidedness))
    return verdicts, exact, whole + half_x + half_y + half_t


def _completions_line(hyp, outcomes):
    """Say whether the rule's verdict would hold whatever the missing pairs said. Reported
    only, except for the lift."""
    verdicts, exact, m = outcomes
    seen = [v for v in ("SUPPORTED", "REFUTED", "INCONCLUSIVE") if v in verdicts]
    if exact:
        spread = "p from %s to %s" % (stats.p_text(min(exact)), stats.p_text(max(exact)))
    else:
        spread = "p not computed"
    if len(seen) == 1:
        text = "settled: %s" % seen[0]
    else:
        text = "unsettled: %s possible" % ", ".join(seen)
    return "hypothesis %s completions (missing pairs: %d): %s; %s" % (hyp.name, m, text, spread)


def aa_gate(plan, aa_valid, aa_planned):
    """(state, non-TIE reads, valid reads) of the A/A gate over valid blind A/A reads. The
    A/A arm is not paired: every non-TIE read counts, ``slightly`` included."""
    non_tie = len([x for x in aa_valid if x.reply.choice != "TIE"])
    if aa_planned == 0 or len(aa_valid) < aa_planned:
        return "not evaluated", non_tie, len(aa_valid)
    if Fraction(non_tie, len(aa_valid)) >= plan.noise_threshold:
        return "tripped", non_tie, len(aa_valid)
    return "passed", non_tie, len(aa_valid)


def aa_side_counts(pairs):
    """(A/A pairs that pick a side, valid A/A pairs) over the A/A pairs in ``pairs``. A valid
    pair picks a side when both its reads are non-TIE, at any strength, and name different
    slots. The slot letters are tested, not ``pair_pick``: on the A/A arm both slots hold one
    version, so ``pair_pick`` would return it for two reads that name the same slot."""
    valid = [p for p in pairs if p.arm == AA and p.status == "valid"]
    picking = [p for p in valid
               if p.first.reply.choice != "TIE" and p.second.reply.choice != "TIE"
               and _pick(p.first)[1] != _pick(p.second)[1]]
    return len(picking), len(valid)


def band_of(gate, aa_pairs, planned):
    """(band, k, n) of a run with ``aa-band: on``, or None when the band is not evaluated:
    the A/A gate is evaluated, there is a valid A/A pair and ``planned`` blind pairs of the
    comparison arm. The band is ``ceil(k * planned / n)`` in whole numbers, in pairs."""
    if gate == "not evaluated":
        return None
    k, n = aa_side_counts(aa_pairs)
    if n < 1 or planned < 1:
        return None
    return -(-k * planned // n), k, n


def sensitivity_gate(plan, sens_pairs):
    """(state, pairs preferring X, valid pairs, planned pairs) of the sensitivity gate over
    the blind readers' sensitivity pairs; "not tested" without a pair."""
    if plan.sensitivity is None:
        return "not tested", 0, 0, 0
    valid, picks, _ties = pair_counts(sens_pairs)
    planned = len(sens_pairs)
    k = picks.get(plan.sensitivity[0], 0)
    if planned == 0 or valid < planned:
        return "not evaluated", k, valid, planned
    if Fraction(k, valid) < plan.sensitivity_threshold:
        return "failed", k, valid, planned
    return "passed", k, valid, planned


def gate_reasons(gate, sens_gate):
    """The reasons the two gates give every comparison verdict, in order."""
    reasons = []
    if gate == "tripped":
        reasons.append("the A/A gate tripped")
    elif gate == "not evaluated":
        reasons.append("the A/A gate was not evaluated")
    if sens_gate == "failed":
        reasons.append("the sensitivity gate failed: the readers did not detect the "
                       "planted difference")
    elif sens_gate == "not evaluated":
        reasons.append("the sensitivity gate was not evaluated")
    return reasons


def hypothesis_verdict(plan, hyp, pairs, gate_reasons_, position, band=None):
    """Score one hypothesis on its arm's pairs (blind readers only). ``gate_reasons_`` are the
    gates' reasons and ``position`` the arm's position state. ``band`` is the (band, k, n) of
    ``band_of`` for a plan with ``aa-band: on`` whose band is evaluated, else None. Returns a
    dict: ``verdict``, ``decider`` (the deciding clause or None), ``reasons``, ``lifted``,
    ``valid``, ``picks``, ``ties``, ``outcomes`` (the completions, or None when no pair is
    short) and ``margin`` (None, or what a SUPPORTED verdict was tested with: the margin, the
    version the deciding clause names, its picks, the other version and its picks). A
    SUPPORTED verdict whose margin is no bigger than the band becomes TIE."""
    first, second = plan.comparisons[hyp.comparison - 1]
    valid, picks, ties = pair_counts(pairs)
    verdict, decider = rule_verdict(hyp, valid, picks)
    reasons = list(gate_reasons_)
    if reasons:
        verdict = "INCONCLUSIVE"
    if position == "INCONCLUSIVE":
        verdict = "INCONCLUSIVE"
        reasons.append("position is INCONCLUSIVE on c%d" % hyp.comparison)
    floor = plan.min_valid_reads
    below = floor is not None and valid < floor
    if below:
        verdict = "INCONCLUSIVE"
        reasons.append("below the read floor (%d valid pairs, floor %d)" % (valid, floor))
    outcomes = None
    if any(p.status != "valid" for p in pairs):
        outcomes = completion_outcomes(plan, hyp, pairs, first, second)
    # a lift: settled under every completion, and nothing but the rule made it INCONCLUSIVE
    lifted = False
    if (floor is not None and not below and not reasons and verdict == "INCONCLUSIVE"
            and outcomes is not None and len(outcomes[0]) == 1
            and next(iter(outcomes[0])) in ("SUPPORTED", "REFUTED")):
        verdict = next(iter(outcomes[0]))
        lifted = True
        reasons.append("lifted from INCONCLUSIVE: settled under every completion of %d "
                       "missing pairs; read floor of %d pairs met" % (outcomes[2], floor))
        for kind, clause in hyp.clauses:
            if kind == verdict:
                decider = clause
                break
    # the family rule, on the verdict as it now stands (a lifted one included)
    family_reason = family_check(plan, verdict, decider, pairs)
    if family_reason is not None:
        verdict = "INCONCLUSIVE"
        reasons = [family_reason]
        lifted = False
    # the band, on the verdict as it now stands (a lifted one included)
    margin = None
    if band is not None and verdict == "SUPPORTED":
        other = first if decider.version == second else second
        margin = (picks.get(decider.version, 0) - picks.get(other, 0), decider.version,
                  picks.get(decider.version, 0), other, picks.get(other, 0))
        if margin[0] <= band[0]:
            verdict = "TIE"
    if verdict == "INCONCLUSIVE":
        decider = None
    return dict(verdict=verdict, decider=decider, reasons=reasons, lifted=lifted,
                valid=valid, picks=picks, ties=ties, outcomes=outcomes,
                family_reason=family_reason, margin=margin)


ONE_WAY = "; the verdict holds only when slightly counts as a pick"


def second_reading(hyp, pairs, gate_reasons_):
    """The hypothesis scored a second time by its frozen rule, with every ``slightly`` read
    counted as a TIE before pairing, under the same gates. Position, the read floor, the
    family rule and the lift do not act on it; it never changes a verdict."""
    valid, picks, _ties = pair_counts(pairs, slightly_tie=True)
    if gate_reasons_:
        return "INCONCLUSIVE"
    return rule_verdict(hyp, valid, picks)[0]


def blind_families(plan):
    """The distinct families of the plan's blind readers, in order of first appearance."""
    found = []
    for reader in plan.readers:
        if not reader.not_blind and reader.family not in found:
            found.append(reader.family)
    return found


def family_check(plan, verdict, decider, pairs):
    """The family rule's reason when it makes a SUPPORTED or REFUTED verdict INCONCLUSIVE,
    else None. ``pairs`` are the arm's pairs of blind readers. The rule applies when the
    version the deciding clause names was drafted or edited by a model of a blind reader's
    family; then the blind readers of every other family, pooled, need at least 3 valid
    pairs, and the clause's share of them (its count over the arm's planned pairs, rounded
    up) must pick the version. A version drafted by ``unknown`` is checked once with each
    blind family as its drafter, and the first check that fails gives the reason."""
    if verdict not in ("SUPPORTED", "REFUTED") or decider is None:
        return None
    who = plan.drafted_by.get(decider.version)
    families = blind_families(plan)
    if who == "unknown":
        runs = [(family,) for family in families]
    elif isinstance(who, tuple):
        runs = [who]
    else:
        return None
    family_of = dict((r.name, r.family) for r in plan.readers)
    share = Fraction(decider.k, len(pairs)) if pairs else Fraction(0)
    for drafters in runs:
        if not any(family in drafters for family in families):
            continue
        others = [family for family in families if family not in drafters]
        if not others:
            return "no reader of another family"
        theirs = [p for p in pairs if p.status == "valid" and family_of.get(p.reader) in others]
        if len(theirs) < FAMILY_MIN_PAIRS:
            return "too few pairs from another family"
        need = math.ceil(share * len(theirs))
        if len([p for p in theirs if pair_pick(p) == decider.version]) < need:
            return "the other family did not agree"
    return None


def family_counts(plan, pairs, version):
    """(family, pairs picking ``version``, valid pairs) for each blind family, in order."""
    family_of = dict((r.name, r.family) for r in plan.readers)
    out = []
    for family in blind_families(plan):
        mine = [p for p in pairs if p.status == "valid" and family_of.get(p.reader) == family]
        out.append((family, len([p for p in mine if pair_pick(p) == version]), len(mine)))
    return out


def _load_run(folder):
    """(planned reads, score records) of an earlier run's folder, read and never written."""
    log = harness.load_log(folder)
    reads = [PlannedRead(*row) for row in harness.load_key(folder, 4)]
    records = harness.records(folder, reads, log.get("cut") == "yes" or
                              log.get("stopped") is not None, harness.log_failures(log),
                              parse_reply)
    return reads, records


def _blind_of(plan, reads, records):
    """(blind planned reads, blind score records) of a run under its own plan."""
    not_blind = set(r.name for r in plan.readers if r.not_blind)
    return ([r for r in reads if r.reader not in not_blind],
            [x for x in records if x.read.reader not in not_blind])


def _pool_runs(plan_path, plan):
    """(blind planned reads, blind score records) of each run this plan's ``aa-pool`` names,
    in order, each under its own plan."""
    folder = harness.folder_of(plan_path)
    found = []
    for item in plan.aa_pool:
        pooled_path = os.path.join(folder, item)[:-len(harness.FREEZE_SUFFIX)]
        pooled_plan = parse(pooled_path)
        reads, records = _load_run(os.path.dirname(pooled_path))
        found.append(_blind_of(pooled_plan, reads, records))
    return found


def _pool_of(plan_path, plan):
    """(valid blind A/A reads, planned blind A/A reads, runs) of the runs this plan's
    ``aa-pool`` names. Only each pooled run's own A/A reads are pooled."""
    valid, planned = [], 0
    for blind_reads, blind_records in _pool_runs(plan_path, plan):
        planned += len([r for r in blind_reads if r.arm == AA])
        valid += [x for x in blind_records if x.read.arm == AA and x.status == "valid"]
    return valid, planned, len(plan.aa_pool)


def _pool_aa_pairs(plan_path, plan):
    """The A/A pairs of the runs this plan's ``aa-pool`` names, each formed inside its own
    run: pairs are never formed across runs."""
    pairs = []
    for _blind_reads, blind_records in _pool_runs(plan_path, plan):
        pairs += pairs_of([x for x in blind_records if x.read.arm == AA])
    return pairs


def arm_position(valid):
    """(state, reads in slot A, non-TIE reads) of one arm's valid reads."""
    slots = [s for s in (_pick(x)[1] for x in valid) if s is not None]
    in_a = len([s for s in slots if s == "A"])
    if len(slots) < 2:
        return "not assessable", in_a, len(slots)
    if in_a in (0, len(slots)):
        return "INCONCLUSIVE", in_a, len(slots)
    return "no slot bias", in_a, len(slots)


class FirstRun(object):
    """What an extension reads of its first run: its plan and its reads, and the verdicts its
    own result would give from those reads alone under its own plan."""

    def __init__(self, plan_path, plan):
        self.plan_path = plan_path
        self.plan = plan
        self.reads, self.records = _load_run(os.path.dirname(plan_path))
        self.blind_reads, self.blind_records = _blind_of(plan, self.reads, self.records)
        self.pairs = pairs_of(self.blind_records)

    def pairs_in(self, arm):
        return [p for p in self.pairs if p.arm == arm]

    def valid_in(self, arm):
        return [x for x in self.blind_records if x.read.arm == arm and x.status == "valid"]

    def verdicts(self):
        """The first run's own verdict of each of its hypotheses, by name."""
        plan = self.plan
        pool_valid, pool_planned, _runs = _pool_of(self.plan_path, plan)
        aa_valid = self.valid_in(AA) + pool_valid
        aa_planned = len([r for r in self.blind_reads if r.arm == AA]) + pool_planned
        gate = aa_gate(plan, aa_valid, aa_planned)[0]
        sens = sensitivity_gate(plan, self.pairs_in(SENS))[0]
        gates = gate_reasons(gate, sens)
        band = None
        if plan.aa_band:
            # the first run's own band: its own A/A pairs and its own pool's, over its own pairs
            band = band_of(gate, self.pairs_in(AA) + _pool_aa_pairs(self.plan_path, plan),
                           len(self.pairs_in("c1")))
        found = {}
        for hyp in plan.hypotheses:
            arm = "c%d" % hyp.comparison
            position = arm_position(self.valid_in(arm))[0]
            found[hyp.name] = hypothesis_verdict(plan, hyp, self.pairs_in(arm), gates,
                                                 position, band)["verdict"]
        return found


def _extension_of(plan_path, plan):
    """The FirstRun an extension reads, or None for a plan that extends nothing."""
    if plan.extends is None:
        return None
    folder = harness.folder_of(plan_path)
    return FirstRun(os.path.join(folder, plan.extends)[:-len(harness.FREEZE_SUFFIX)],
                    parse(os.path.join(folder, plan.extends)[:-len(harness.FREEZE_SUFFIX)]))


def _score_and_write(plan_path, plan, recorded, freeze_hash, now=None, environ=None):
    with harness.unlimited_int_digits():
        return _score_and_write_unlimited(plan_path, plan, recorded, freeze_hash, now, environ)


def _series_after(result, plan, plan_path, recorded, verdicts, now, environ=None):
    """The series file's write, after the result file exists (series spec section 5). A result
    with exit status 2 changes nothing. The ``series:`` line is added to the printed text, never
    to the result file; a failed write raises the exit status to 1 and nothing more."""
    if result.exit_code not in (0, 1):
        return result
    line, warning, failed = series.after_result(plan, plan_path, recorded, verdicts, now,
                                                environ)
    result.text += line + "\n"
    result.warnings += warning
    if failed:
        result.exit_code = max(result.exit_code, 1)
    return result


def _score_and_write_unlimited(plan_path, plan, recorded, freeze_hash, now=None, environ=None):
    folder = harness.folder_of(plan_path)
    log = harness.load_log(folder)
    cut = log.get("cut") == "yes"
    stopped = log.get("stopped")
    reads = [PlannedRead(*row) for row in harness.load_key(folder, 4)]
    failures = harness.log_failures(log)
    records = harness.records(folder, reads, cut or stopped is not None, failures,
                              parse_reply)
    arms = _arms(plan)
    not_blind = set(r.name for r in plan.readers if r.not_blind)
    # I-1 (C:152, § 6): every verdict, gate, count, position and score below uses blind
    # readers' reads only, planned reads included. The per-read rows, the key and slot
    # lines, the not-blind reads line, DEAD and the tail still cover every reader.
    blind_records = [x for x in records if x.read.reader not in not_blind]
    blind_reads = [r for r in reads if r.reader not in not_blind]
    # an extension reads its first run's reads pooled with its own, its rules at the pooled
    # pairs; a plan that pools A/A reads gates on them too
    ext = _extension_of(plan_path, plan)
    scoring = plan
    if ext is not None:
        scoring = copy.copy(plan)
        scoring.hypotheses, scoring.mechanisms, _problems = _scaled_rules(plan, ext.plan)
        names = set(r.name for r in plan.readers)
        scoring.readers = plan.readers + [r for r in ext.plan.readers
                                          if r.name not in names]
    pool_valid, pool_planned, pool_runs = _pool_of(plan_path, plan)
    first_blind = None
    if plan.replicate_of is not None:
        # The first run's folder is read, never written.
        first_folder = _first_folder(plan_path, plan)
        first_log = harness.load_log(first_folder)
        first_cut = first_log.get("cut") == "yes"
        first_stopped = first_log.get("stopped")
        first_reads = [PlannedRead(*row) for row in harness.load_key(first_folder, 4)]
        first_records = harness.records(first_folder, first_reads,
                                        first_cut or first_stopped is not None,
                                        harness.log_failures(first_log), parse_reply)
        first_blind = [x for x in first_records if x.read.reader not in not_blind]
    out = []

    out.append("plan sha256: %s" % _show(recorded.get(os.path.basename(plan_path), "unknown")))
    out.append("freeze sha256: %s" % freeze_hash)
    if plan.amends is not None:
        out.append("amended freeze sha256: %s" % _show(recorded.get(plan.amends, "unknown")))
    out.append("prompt sha256: %s" % _show(recorded.get(PROMPT_LABEL, "unknown")))
    if plan.document != RESUME:
        out.append("document: %s" % plan.document)
    if plan.extends is not None:
        out.append("extends: %s; the sample size changed after a result was seen"
                   % _show(recorded.get(plan.extends, "unknown")))
    if plan.replicate_of is not None:
        out.append("replicate of: %s" % _show(recorded.get(plan.replicate_of, "unknown")))
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

    def valid_in(arm):
        """The valid reads of a blind reader in this arm."""
        return [x for x in blind_records if x.read.arm == arm and x.status == "valid"]

    def pooled_valid_in(arm):
        """The valid blind reads of this run, and of the first run when this plan extends."""
        return (ext.valid_in(arm) if ext is not None else []) + valid_in(arm)

    def valid_not_blind_in(arm):
        """The valid reads of a reader marked not-blind in this arm."""
        return [x for x in records if x.read.arm == arm and x.status == "valid"
                and x.read.reader in not_blind]

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

    # reads, blind readers (all readers when none is marked not-blind) and not-blind readers
    first_label = "blind readers" if not_blind else "all readers"
    for arm, first, second in arms:
        for label, recs in ((first_label, valid_in(arm)),
                            ("not-blind readers", valid_not_blind_in(arm))):
            picks, ties = picks_in(recs)
            versions = [first] if first == second else [first, second]
            out.append("reads %s %s: valid=%d %s tie=%d" % (
                label, arm, len(recs),
                " ".join("%s=%d" % (v, picks.get(v, 0)) for v in versions), ties))

    # the pairs of blind readers, per arm (the A/A arm is not paired)
    blind_pairs = pairs_of(blind_records)

    def pairs_in(arm):
        return [p for p in blind_pairs if p.arm == arm]

    def pooled_pairs_in(arm):
        """The pairs of both runs when this plan extends; pairs are never formed across runs."""
        return (ext.pairs_in(arm) if ext is not None else []) + pairs_in(arm)

    def left_out_in(arm):
        found = len(valid_not_blind_in(arm))
        if ext is not None:
            out_names = set(r.name for r in ext.plan.readers if r.not_blind)
            found += len([x for x in ext.records if x.read.arm == arm
                          and x.status == "valid" and x.read.reader in out_names])
        return found

    # missing reads, per arm, and a dead run
    for arm, _first, _second in arms:
        mine = [x for x in blind_records if x.read.arm == arm]
        failed = len([x for x in mine if x.status == "failed"])
        not_run = len([x for x in mine if x.status not in ("valid", "failed")])
        line = ("missing %s: %d of %d planned reads (failed %d, not run %d)"
                % (arm, failed + not_run, len([r for r in blind_reads if r.arm == arm]),
                   failed, not_run))
        if arm != AA:
            short_pairs = len([p for p in pairs_in(arm) if p.status != "valid"])
            line += ", costing %d of %d planned pairs" % (short_pairs, len(pairs_in(arm)))
        out.append(line)
    if ext is not None:
        for arm, _first, _second in arms:
            out.append("extension pool %s: first run %d valid reads of %d planned, this run "
                       "%d of %d" % (arm, len(ext.valid_in(arm)),
                                     len([r for r in ext.blind_reads if r.arm == arm]),
                                     len(valid_in(arm)),
                                     len([r for r in blind_reads if r.arm == arm])))
    if not any(x.status == "valid" for x in records):
        out.append("DEAD: 0 of %d planned reads are valid" % len(reads))

    # A/A gate: every non-TIE read counts, slightly included
    aa_own = valid_in(AA)
    aa_planned = (len([r for r in blind_reads if r.arm == AA]) + pool_planned
                  + (len([r for r in ext.blind_reads if r.arm == AA])
                     if ext is not None else 0))
    aa_valid = pooled_valid_in(AA) + pool_valid
    gate, aa_non_tie, aa_count = aa_gate(plan, aa_valid, aa_planned)
    if plan.aa_pool:
        out.append("A/A pool: %d earlier runs, %d valid A/A reads in the gate"
                   % (pool_runs, len(aa_valid)))
    if gate == "not evaluated":
        out.append("A/A gate: not evaluated (%d valid reads of %d planned)"
                   % (aa_count, aa_planned))
    elif gate == "tripped":
        out.append("A/A gate: tripped (%d of %d valid A/A reads non-TIE, at any strength, "
                   "%s; threshold %s)" % (aa_non_tie, aa_count,
                                          _percent(aa_non_tie, aa_count),
                                          plan.noise_threshold))
    else:
        out.append("A/A gate: passed (%d of %d valid A/A reads non-TIE, at any strength; "
                   "threshold %s)" % (aa_non_tie, aa_count, plan.noise_threshold))
    # sensitivity gate: of the blind readers' valid sensitivity pairs, how many prefer X
    sens_gate, sens_k, sens_n, sens_planned = sensitivity_gate(plan, pooled_pairs_in(SENS))
    if sens_gate == "not evaluated":
        out.append("sensitivity gate: not evaluated (%d valid pairs of %d planned)"
                   % (sens_n, sens_planned))
    elif sens_gate in ("passed", "failed"):
        out.append("sensitivity gate: %s (%d of %d valid sensitivity pairs prefer %s; "
                   "threshold %s)" % (sens_gate, sens_k, sens_n, plan.sensitivity[0],
                                      plan.sensitivity_threshold))
        low, high = stats.wilson(sens_k, sens_n)
        out.append("sensitivity gate evidence: p = %s one-sided greater (reads may be "
                   "correlated; may be too small); 95%% interval %s to %s"
                   % (stats.p_text(stats.binomial_p(sens_k, sens_n, "greater")), low, high))
    else:
        out.append("sensitivity gate: not tested")
    if aa_valid:
        low, high = stats.wilson(aa_non_tie, aa_count)
        out.append("A/A gate interval: %s to %s (95%%, Wilson)" % (low, high))
    else:
        out.append("A/A gate interval: not computed")
    band = None
    if plan.aa_band:
        aa_pairs = (pairs_in(AA) + (ext.pairs_in(AA) if ext is not None else [])
                    + _pool_aa_pairs(plan_path, plan))
        band = band_of(gate, aa_pairs, len(pooled_pairs_in("c1")))
        if band is not None:
            out.append("A/A band: identical drafts picked a side in %d of %d valid A/A pairs; "
                       "band %d pairs" % (band[1], band[2], band[0]))
    slightly = len([x for x in aa_own if x.reply.choice != "TIE"
                    and x.reply.strength == SLIGHTLY])
    out.append("A/A slightly rate: %d of %d valid A/A reads are slightly"
               % (slightly, len(aa_own)))
    gates = gate_reasons(gate, sens_gate)

    # position
    position = {}
    total_a = total_picks = 0
    for arm, _first, _second in arms:
        slots = [_pick(x)[1] for x in pooled_valid_in(arm)]
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
        out.append("position %s: %d of %d non-TIE reads in slot A%s: %s"
                   % (arm, in_a, len(slots), share, position[arm]))
    if total_picks < 2:
        overall = "not assessable"
    elif total_a in (0, total_picks):
        overall = "INCONCLUSIVE"
    else:
        overall = "no slot bias"
    share = "" if not total_picks else " (%s)" % _percent(total_a, total_picks)
    out.append("position overall: %d of %d non-TIE reads in slot A%s: %s"
               % (total_a, total_picks, share, overall))
    # order consistency: of a blind reader's pairs in which both reads pick a version, how
    # many pick the same version in both orders
    for arm, _first, _second in arms:
        if arm == AA:
            continue
        for reader in plan.readers:
            if reader.name in not_blind:
                continue
            both = [p for p in pooled_pairs_in(arm) if p.reader == reader.name
                    and p.status == "valid" and read_version(p.first) is not None
                    and read_version(p.second) is not None]
            same = len([p for p in both if pair_pick(p) is not None])
            out.append("order consistency %s %s: %d of %d pairs pick the same version in "
                       "both orders" % (_show(reader.name), arm, same, len(both)))

    # hypotheses
    first_verdicts = ext.verdicts() if ext is not None else {}
    verdict_words = []
    for index, hyp in enumerate(scoring.hypotheses):
        arm = "c%d" % hyp.comparison
        first_version, second = plan.comparisons[hyp.comparison - 1]
        rule = ["%s if %s" % (kind, clause.text()) for kind, clause in plan.hypotheses[index].clauses]
        pooled_rule = ["%s if %s" % (kind, clause.text()) for kind, clause in hyp.clauses]
        scored = hypothesis_verdict(scoring, hyp, pooled_pairs_in(arm), gates, position[arm],
                                    band)
        verdict, decider, reasons = scored["verdict"], scored["decider"], scored["reasons"]
        verdict_words.append((hyp.name, verdict))
        lifted, picks, ties, outcomes = (scored["lifted"], scored["picks"], scored["ties"],
                                         scored["outcomes"])
        out.append("hypothesis %s rule: %s" % (hyp.name, "; ".join(rule) or "none"))
        if ext is not None:
            out.append("hypothesis %s rule at the pooled pairs: %s"
                       % (hyp.name, "; ".join(pooled_rule) or "none"))
        out.append("hypothesis %s pair counts: valid=%d %s=%d %s=%d tie=%d" % (
            hyp.name, scored["valid"], first_version, picks.get(first_version, 0), second,
            picks.get(second, 0), ties))
        left_out = left_out_in(arm)
        second_verdict = second_reading(hyp, pooled_pairs_in(arm), gates)
        one_way = (ONE_WAY if verdict in ("SUPPORTED", "REFUTED") and second_verdict != verdict
                   else "")
        out.append("hypothesis %s verdict: %s%s [not blind: %d reads left out]"
                   % (hyp.name, verdict, one_way, left_out))
        if verdict == "TIE":
            out.append("TIE: %s: the margin of %d pairs is inside this run's A/A band "
                       "(identical drafts picked a side in %d of %d pairs). The versions are "
                       "not shown to differ." % (hyp.name, scored["margin"][0], band[1], band[2]))
        else:
            for reason in reasons:
                out.append("hypothesis %s reason: %s" % (hyp.name, reason))
        out.append("hypothesis %s second reading (slightly as TIE): %s"
                   % (hyp.name, second_verdict))
        if scored["margin"] is not None:
            out.append("hypothesis %s margin: %d pairs (%s %d picks, %s %d picks) against "
                       "band %d pairs" % ((hyp.name,) + scored["margin"] + (band[0],)))
        for family, k_family, n_family in family_counts(scoring, pooled_pairs_in(arm), second):
            out.append("hypothesis %s family %s: %s %d of %d paired picks"
                       % (hyp.name, _show(family), _show(second), k_family, n_family))
        n = sum(picks.values())
        if n == 0:
            out.append("hypothesis %s evidence: no non-TIE paired pick, %d TIE; "
                       "p and interval not computed" % (hyp.name, ties))
        else:
            k = picks.get(second, 0)
            p = stats.binomial_p(k, n, plan.sidedness)
            low, high = stats.wilson(k, n)
            out.append("hypothesis %s evidence: %s %d of %d non-TIE paired picks, %d TIE; "
                       "p = %s %s (reads may be correlated; may be too small); "
                       "95%% interval %s to %s" % (
                           hyp.name, _show(second), k, n, ties, stats.p_text(p),
                           SIDE_TEXT[plan.sidedness], low, high))
            if verdict == "TIE" or (reasons and not lifted):
                pass
            elif verdict in ("SUPPORTED", "REFUTED"):
                tested = second if plan.sidedness == "greater" else first_version
                if plan.sidedness != "two" and decider.version != tested:
                    out.append("hypothesis %s flag: one-sided test: this direction not tested"
                               % hyp.name)
                elif p >= plan.alpha:
                    out.append("hypothesis %s flag: evidence disagrees: %s at p = %s, "
                               "at or above alpha %s" % (hyp.name, verdict, stats.p_text(p),
                                                         plan.alpha_text))
            elif p < plan.alpha:
                out.append("hypothesis %s flag: evidence disagrees: INCONCLUSIVE at p = %s, "
                           "below alpha %s" % (hyp.name, stats.p_text(p), plan.alpha_text))
        if outcomes is not None:
            out.append(_completions_line(hyp, outcomes))
        if first_blind is not None:
            _v1, first_picks, _t1 = pair_counts([p for p in pairs_of(first_blind)
                                                 if p.arm == arm])
            k1, n1 = first_picks.get(second, 0), sum(first_picks.values())
            out.append("hypothesis %s replicate: first run %s %d of %d paired picks, "
                       "this run %d of %d; "
                       "Fisher exact p = %s two-sided"
                       % (hyp.name, _show(second), k1, n1, picks.get(second, 0), n,
                          stats.p_text(stats.fisher_p(k1, n1, picks.get(second, 0), n))))
        if ext is not None:
            out.append("hypothesis %s extension: first run %s, pooled %s"
                       % (hyp.name, first_verdicts[hyp.name], verdict))

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

    for mech in scoring.mechanisms:
        arm = "c%d" % mech.comparison
        label = "mechanism %s in %s" % (_show(mech.name), arm)
        recs = pooled_valid_in(arm)
        floor_recs = pooled_valid_in(AA)
        count, floor = matching(recs, mech), matching(floor_recs, mech)
        out.append("%s count: %d of %d valid reads" % (label, count, len(recs)))
        out.append("%s A/A floor: %d of %d valid reads" % (label, floor, len(floor_recs)))
        separates = bool(recs and floor_recs
                         and Fraction(count, len(recs)) > Fraction(floor, len(floor_recs)))
        if separates:
            out.append("%s separation: separates the versions from the A/A floor" % label)
            verdict = "SUPPORTED" if count >= mech.k else "INCONCLUSIVE"
        else:
            out.append("%s separation: unable to separate the versions" % label)
            verdict = "INCONCLUSIVE"
        reasons = []
        # the margin: two-sided Fisher exact p of the arm's count against the A/A floor,
        # below the plan's alpha
        if recs and floor_recs:
            margin = stats.fisher_p(count, len(recs), floor, len(floor_recs))
            out.append("%s margin: Fisher exact p = %s two-sided against the A/A floor"
                       % (label, stats.p_text(margin)))
            if separates and margin >= plan.alpha:
                verdict = "INCONCLUSIVE"
                reasons.append("no margin over the A/A floor")
        else:
            out.append("%s margin: not computed (an arm has no valid read)" % label)
        if gates:
            verdict = "INCONCLUSIVE"
            reasons += gates
        valid_pairs = pair_counts(pooled_pairs_in(arm))[0]
        if plan.min_valid_reads is not None and valid_pairs < plan.min_valid_reads:
            verdict = "INCONCLUSIVE"
            reasons.append("below the read floor (%d valid pairs, floor %d)"
                           % (valid_pairs, plan.min_valid_reads))
        left_out = left_out_in(arm)
        out.append("%s verdict: %s (SUPPORTED at %d or more) (what readers wrote, not a cause) "
                   "[not blind: %d reads left out]" % (label, verdict, mech.k, left_out))
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
    for arm, _first, _second in arms:
        recs = valid_in(arm)
        ceiling = len([x for x in recs
                       if x.reply.score_a >= 10 and x.reply.score_b >= 10])
        same = len([x for x in recs if x.reply.score_a == x.reply.score_b])
        out.append("scores %s ceiling: %d of %d valid reads score both slots at 10 or more"
                   % (arm, ceiling, len(recs)))
        out.append("scores %s separation: %d of %d valid reads give both slots the same score"
                   % (arm, same, len(recs)))
        if recs and ceiling == len(recs):
            out.append("scores %s: at the ceiling; preference is the only measure" % arm)
    if plan.sensitivity is not None:
        sens_x, sens_w = plan.sensitivity
        for reader in plan.readers:
            if reader.name in not_blind:
                continue
            mine = {sens_x: [], sens_w: []}
            for x in valid_in(SENS):
                if x.read.reader != reader.name:
                    continue
                for version, mark in ((x.read.slot_a, x.reply.score_a),
                                      (x.read.slot_b, x.reply.score_b)):
                    mine[version].append(mark)
            if mine[sens_x]:
                gap = (Fraction(sum(mine[sens_x]), len(mine[sens_x]))
                       - Fraction(sum(mine[sens_w]), len(mine[sens_w])))
                text = harness.fraction_text(gap)
                if text == "-0.00":
                    text = "0.00"
                out.append("sensitivity score gap %s: %s" % (reader.name, text))
    groups = []
    for reader in plan.readers:
        if reader.group is not None and reader.group not in groups:
            groups.append(reader.group)
    for group in groups:
        names = set(r.name for r in plan.readers if r.group == group)
        out.append("reader-group %s: %d valid reads"
                   % (group, len([x for x in records
                                  if x.status == "valid" and x.read.reader in names])))
    out.append(VALIDITY_LINE)

    result = harness.finish_result(folder, out, records, log, stopped)
    if plan.series is None:
        return result
    return _series_after(result, plan, plan_path, recorded, verdict_words, now, environ)
