"""Tone and tells check: wording in copy that reads against the writer.

The behaviour is stated in docs/specs/tone-and-tells.md. In short: read a rule file,
prove every rule against its own examples, and only then read the input files; flag each
match with its line, level, rule and sentence; fail only on rules set as errors.

The tool never writes a file and never suggests a replacement.
"""

import bisect
import collections
import json
import os
import re
import unicodedata

_DEFAULT_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "data", "tone-default.json")

_RULE_KEYS = ("id", "level", "kind", "text", "case", "category", "rationale",
              "must_fire", "must_not")
_REQUIRED_KEYS = ("id", "level", "kind", "text", "rationale", "must_fire", "must_not")
_EXEMPTION_KEYS = ("rule", "anchor", "reason")
_TOP_KEYS = ("rules", "exemptions")
_LEVELS = ("error", "warn")
_KINDS = ("phrase", "char", "regex")
_CASES = ("insensitive", "sensitive")

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_CLOSERS = "\"'\u201d\u2019)]"
_WHITESPACE_RUN = re.compile(r"\s+")


class ToneError(Exception):
    """The run cannot go ahead. The message is one plain line, without the prefix."""


class Result(object):
    """What a run produced. ``text`` is exactly stdout; ``error`` is the stderr lines
    joined with a line feed, without a final one."""

    def __init__(self, exit_code, ran, text="", error=""):
        self.exit_code = exit_code
        self.ran = ran
        self.text = text
        self.error = error

    def __repr__(self):
        return "Result(exit_code=%r, ran=%r, error=%r)" % (
            self.exit_code, self.ran, self.error)


class RuleSet(object):
    """A loaded rule file: the parsed JSON, not yet checked."""

    def __init__(self, data, duplicate_keys=()):
        self.data = data
        self.duplicate_keys = list(duplicate_keys)
        self._checked = None


Rule = collections.namedtuple("Rule", "id level category rationale find")


# ---------------------------------------------------------------- loading

def default_rules_text():
    """The shipped default rule file, as text. Raises ToneError."""
    return _read_text(_DEFAULT_RULES, "cannot read the rule file",
                      "the rule file is not valid UTF-8")


def _read_text(path, unreadable, not_utf8):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except (OSError, ValueError):
        raise ToneError(unreadable)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ToneError(not_utf8)


def load_rules(path=None):
    """Read and parse a rule file (None: the shipped default). Raises ToneError."""
    text = _read_text(_DEFAULT_RULES if path is None else path,
                      "cannot read the rule file", "the rule file is not valid UTF-8")
    duplicates = []

    def pairs_hook(pairs):
        found = {}
        for key, value in pairs:
            if key in found:
                duplicates.append(key)
            found[key] = value
        return found

    try:
        data = json.loads(text, object_pairs_hook=pairs_hook)
    except (ValueError, RecursionError):
        raise ToneError("the rule file is not valid JSON")
    return RuleSet(data, duplicates)


# ---------------------------------------------------------------- matching

def _is_word_char(ch):
    return ch == "_" or unicodedata.category(ch)[0] in ("L", "N")


def _fold_with_map(text):
    """Full case folding, one source character at a time.

    Returns (folded text, list giving, for each folded character, the index of the
    source character it came from)."""
    pieces = []
    origin = []
    for index, ch in enumerate(text):
        folded = ch.casefold()
        pieces.append(folded)
        origin.extend([index] * len(folded))
    return "".join(pieces), origin


def _phrase_finder(text, insensitive):
    """Spec section 4, phrase: whole words, a space matching one or more whitespace."""
    wanted = _fold_with_map(text)[0] if insensitive else text
    pattern = re.compile("".join(r"\s+" if ch == " " else re.escape(ch) for ch in wanted))
    left_word = _is_word_char(text[0])
    right_word = _is_word_char(text[-1])

    def find(body):
        if insensitive:
            haystack, origin = _fold_with_map(body)
        else:
            haystack, origin = body, None
        found = []
        pos = 0
        while pos <= len(haystack):
            match = pattern.search(haystack, pos)
            if match is None:
                break
            first, last = match.span()
            if origin is None:
                start, end = first, last
                whole = True
            else:
                start, end = origin[first], origin[last - 1] + 1
                whole = ((first == 0 or origin[first - 1] != origin[first])
                         and (last == len(haystack) or origin[last] != origin[last - 1]))
            if (not whole
                    or (left_word and start > 0 and _is_word_char(body[start - 1]))
                    or (right_word and end < len(body) and _is_word_char(body[end]))):
                pos = first + 1
                continue
            found.append((start, end))
            pos = last
        return found

    return find


def _char_finder(text):
    def find(body):
        found = []
        index = body.find(text)
        while index != -1:
            found.append((index, index + 1))
            index = body.find(text, index + 1)
        return found

    return find


def _regex_finder(pattern):
    def find(body):
        return [match.span() for match in pattern.finditer(body)
                if match.end() > match.start()]

    return find


def _single_line(value):
    return isinstance(value, str) and "\n" not in value and "\r" not in value


def _key_text(key):
    return json.dumps(key)


# ---------------------------------------------------------------- self-test

def _check_rule(rule, name, problems):
    """Check one rule's shape. Returns a Rule, or None when it has a problem."""
    start = len(problems)

    def bad(message):
        problems.append("self-test: rule %s: %s" % (name, message))

    if not isinstance(rule, dict):
        bad("is not an object")
        return None
    for key in rule:
        if key not in _RULE_KEYS:
            bad("unknown key %s" % _key_text(key))
    for key in _REQUIRED_KEYS:
        if key not in rule:
            bad("%s is missing" % key)
    kind = rule.get("kind")
    level = rule.get("level")
    text = rule.get("text")
    if "level" in rule and not (isinstance(level, str) and level in _LEVELS):
        bad("level must be error or warn")
    if "kind" in rule and not (isinstance(kind, str) and kind in _KINDS):
        bad("kind must be phrase, char or regex")
    text_ok = False
    if "text" in rule:
        if not isinstance(text, str) or text == "":
            bad("text must be a non-empty string")
        elif kind == "char" and len(text) != 1:
            bad("text of a char rule must be exactly one code point")
        else:
            text_ok = True
    case = rule.get("case", "insensitive")
    if "case" in rule:
        if kind == "char":
            bad("a char rule cannot set case")
        elif not (isinstance(case, str) and case in _CASES):
            bad("case must be insensitive or sensitive")
    if "category" in rule:
        category = rule["category"]
        if (not isinstance(category, str) or category == ""
                or "]" in category or "\n" in category or "\r" in category):
            bad("category must be a non-empty label without ], line feed or carriage return")
    if "rationale" in rule:
        value = rule["rationale"]
        if not _single_line(value) or value == "":
            bad("rationale must be one non-empty line")
    for key in ("must_fire", "must_not"):
        if key in rule:
            value = rule[key]
            if not isinstance(value, list) or not value:
                bad("%s must be a non-empty array of strings" % key)
            elif not all(isinstance(item, str) and item != "" for item in value):
                bad("%s must hold only non-empty strings" % key)
    find = None
    if text_ok and isinstance(kind, str) and kind in _KINDS:
        insensitive = case == "insensitive"
        if kind == "phrase":
            find = _phrase_finder(text, insensitive)
        elif kind == "char":
            find = _char_finder(text)
        else:
            try:
                pattern = re.compile(text, re.IGNORECASE if insensitive else 0)
            except Exception:
                bad("regex does not compile")
            else:
                if pattern.fullmatch("") is not None:
                    bad("regex matches the empty string")
                else:
                    find = _regex_finder(pattern)
    if len(problems) != start or find is None:
        return None
    return Rule(rule["id"], level, rule.get("category"), rule["rationale"], find)


def _check(rule_set):
    """Run the whole self-test. Returns (problems, rules, exemptions)."""
    problems = []
    data = rule_set.data
    for key in rule_set.duplicate_keys:
        problems.append("self-test: duplicate key %s" % _key_text(key))
    if not isinstance(data, dict):
        problems.append("self-test: the rule file must be a JSON object")
        return problems, [], []
    for key in data:
        if key not in _TOP_KEYS:
            problems.append("self-test: unknown key %s" % _key_text(key))
    raw_rules = data.get("rules")
    if "rules" not in data:
        problems.append("self-test: rules is missing")
        raw_rules = []
    elif not isinstance(raw_rules, list) or not raw_rules:
        problems.append("self-test: rules must be a non-empty array")
        raw_rules = []
    raw_exemptions = data.get("exemptions", [])
    if not isinstance(raw_exemptions, list):
        problems.append("self-test: exemptions must be an array")
        raw_exemptions = []

    seen = {}
    for position, rule in enumerate(raw_rules, 1):
        rule_id = rule.get("id") if isinstance(rule, dict) else None
        if isinstance(rule_id, str) and re.fullmatch(r"[a-z0-9-]+", rule_id):
            name = rule_id
            seen.setdefault(rule_id, []).append(position)
        else:
            name = "#%d" % position
            if isinstance(rule, dict) and "id" in rule:
                problems.append("self-test: rule %s: id must be lower-case letters, "
                                "digits and hyphens" % name)
    for rule_id, positions in seen.items():
        if len(positions) > 1:
            problems.append("self-test: rule %s: id is used more than once" % rule_id)

    rules = []
    levels = {}
    for position, rule in enumerate(raw_rules, 1):
        rule_id = rule.get("id") if isinstance(rule, dict) else None
        valid_id = isinstance(rule_id, str) and re.fullmatch(r"[a-z0-9-]+", rule_id)
        name = rule_id if valid_id else "#%d" % position
        if valid_id and isinstance(rule.get("level"), str):
            levels.setdefault(rule_id, rule["level"])
        built = _check_rule(rule, name, problems)
        if built is None:
            continue
        failed = False
        for key, should_fire in (("must_fire", True), ("must_not", False)):
            for number, example in enumerate(rule[key], 1):
                try:
                    fires = len(built.find(example)) > 0
                except Exception:
                    problems.append("self-test: rule %s: %s example %d could not be "
                                    "checked" % (name, key, number))
                    failed = True
                    continue
                if should_fire and not fires:
                    problems.append("self-test: rule %s: must_fire example %d gives no "
                                    "finding" % (name, number))
                    failed = True
                elif not should_fire and fires:
                    problems.append("self-test: rule %s: must_not example %d gives a "
                                    "finding" % (name, number))
                    failed = True
        if not failed:
            rules.append(built)

    exemptions = []
    for number, item in enumerate(raw_exemptions, 1):
        label = "self-test: exemption %d: " % number
        if not isinstance(item, dict):
            problems.append(label + "is not an object")
            continue
        start = len(problems)
        for key in item:
            if key not in _EXEMPTION_KEYS:
                problems.append(label + "unknown key %s" % _key_text(key))
        for key in _EXEMPTION_KEYS:
            if key not in item:
                problems.append(label + "%s is missing" % key)
        target = item.get("rule")
        if "rule" in item:
            if not isinstance(target, str) or target not in levels:
                problems.append(label + "names no rule")
            elif levels[target] != "error":
                problems.append(label + "names a rule that is not an error rule")
        if "anchor" in item and (not isinstance(item["anchor"], str)
                                 or item["anchor"] == ""):
            problems.append(label + "anchor must be a non-empty string")
        if "reason" in item and (not _single_line(item["reason"]) or item["reason"] == ""):
            problems.append(label + "reason must be one non-empty line")
        if len(problems) == start:
            exemptions.append((item["rule"], item["anchor"]))
    return problems, rules, exemptions


def self_test(rule_set):
    """Check a rule set against section 6. Returns the problem lines (empty: it passes)."""
    try:
        problems, rules, exemptions = _check(rule_set)
    except Exception:
        return ["self-test: the rule file could not be checked"]
    rule_set._checked = (rules, exemptions) if not problems else None
    return problems


# ---------------------------------------------------------------- reading a file

def _line_starts(text):
    starts = [0]
    starts.extend(match.end() for match in _LINE_BREAK.finditer(text))
    return starts


def _blank_lines(text, starts):
    """The (start, end) of each blank line, its line break included in the end."""
    found = []
    for number, start in enumerate(starts):
        if number + 1 < len(starts):
            end = starts[number + 1]
            content = text[start:end].rstrip("\r\n")
        else:
            end = len(text)
            content = text[start:end]
            if content == "":
                continue
        if content.strip(" \t") == "":
            found.append((start, end))
    return found


def _sentence_ends(text):
    ends = set()
    size = len(text)
    for index, ch in enumerate(text):
        if ch in ".!?":
            j = index + 1
            while j < size and text[j] in _CLOSERS:
                j += 1
            if j == size or text[j].isspace():
                ends.add(j)
    return sorted(ends)


def _pieces(text, starts):
    """The sentences of a text, as (start, end) pairs (spec section 7)."""
    ends = _sentence_ends(text)
    blanks = _blank_lines(text, starts)
    blank_starts = [b[0] for b in blanks]
    size = len(text)
    found = []
    pos = 0
    while pos < size:
        inside = bisect.bisect_right(blank_starts, pos) - 1
        if inside >= 0 and blanks[inside][0] <= pos < blanks[inside][1]:
            pos = blanks[inside][1]
            continue
        end = size
        resume = size
        k = bisect.bisect_right(ends, pos)
        if k < len(ends):
            end = ends[k]
            resume = end
        b = bisect.bisect_left(blank_starts, pos)
        if b < len(blanks) and blanks[b][0] < end:
            end = blanks[b][0]
            resume = blanks[b][1]
        if text[pos:end].strip() != "":
            found.append((pos, end))
        pos = resume
    return found


class _Body(object):
    """One input file's text, with what its findings need."""

    def __init__(self, text):
        self.text = text
        self.starts = _line_starts(text)
        self._pieces = None
        self._piece_starts = None

    def line_of(self, position):
        return bisect.bisect_right(self.starts, position)

    def sentence(self, start, end):
        if self._pieces is None:
            self._pieces = _pieces(self.text, self.starts)
            self._piece_starts = [p[0] for p in self._pieces]
        pieces = self._pieces
        piece_starts = self._piece_starts
        first = bisect.bisect_right(piece_starts, start) - 1
        if first < 0 or start >= pieces[first][1]:
            first += 1
        last = bisect.bisect_right(piece_starts, end - 1) - 1
        if first >= len(pieces) or last < 0 or first > last:
            return ""
        shown = self.text[pieces[first][0]:pieces[last][1]]
        return _WHITESPACE_RUN.sub(" ", shown).strip()


def _anchored(text, anchor, start, end):
    """True when [start, end) lies wholly inside an occurrence of anchor in text."""
    index = text.find(anchor)
    while index != -1:
        if index <= start and end <= index + len(anchor):
            return True
        index = text.find(anchor, index + 1)
    return False


# ---------------------------------------------------------------- the run

def _label(name):
    return name.replace("\r", "?").replace("\n", "?")


def _cannot(lines):
    return Result(2, False, text="", error="\n".join(lines))


def _run(rules_path, files, warn_only, stale_check):
    try:
        rule_set = load_rules(rules_path)
    except ToneError as exc:
        return _cannot(["cannot run: %s" % exc])
    problems = self_test(rule_set)
    if problems:
        return _cannot(problems)
    rules, exemptions = rule_set._checked
    files = list(files)
    if not files:
        return _cannot(["cannot run: no input file"])
    bodies = []
    failures = []
    for name in files:
        try:
            with open(name, "rb") as handle:
                raw = handle.read()
        except (OSError, ValueError):
            failures.append("cannot run: cannot read %s" % _label(name))
            continue
        try:
            bodies.append(_Body(raw.decode("utf-8")))
        except UnicodeDecodeError:
            failures.append("cannot run: %s is not valid UTF-8" % _label(name))
    if failures:
        return _cannot(failures)

    out = []
    errors = 0
    warnings = 0
    for name, body in zip(files, bodies):
        shown = 0
        for rule in rules:
            if warn_only and rule.level != "warn":
                continue
            anchors = [a for r, a in exemptions if r == rule.id] \
                if rule.level == "error" else []
            for start, end in rule.find(body.text):
                if any(_anchored(body.text, a, start, end) for a in anchors):
                    continue
                shown += 1
                if rule.level == "error":
                    errors += 1
                else:
                    warnings += 1
                out.append("%s:%d: %s %s%s: %s\n    %s\n" % (
                    name, body.line_of(start), rule.level, rule.id,
                    "" if rule.category is None else " [%s]" % rule.category,
                    rule.rationale, body.sentence(start, end)))
        if not shown:
            out.append("%s: clean\n" % name)
    if stale_check:
        for rule_id, anchor in exemptions:
            if not any(anchor in body.text for body in bodies):
                out.append("stale exemption: %s\n" % rule_id)
                errors += 1
    out.append("%d file(s), %d error(s), %d warning(s)\n" % (len(files), errors, warnings))
    return Result(1 if errors else 0, True, text="".join(out))


def run(*, rules_path=None, files, warn_only=False, stale_check=False):
    """Check files against a rule file. No exception escapes."""
    try:
        return _run(rules_path, files, warn_only, stale_check)
    except Exception:
        return _cannot(["cannot run: the check failed unexpectedly"])
