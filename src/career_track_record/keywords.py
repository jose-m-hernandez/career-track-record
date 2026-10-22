"""Keyword scan: which terms saved postings ask for that your copy never uses.

Public API: ``load_terms(path)`` and ``run(mode, ...)``. Every way the scan
cannot run comes back as a ``Result`` with ``exit_code`` 2, never as an
exception out of ``run``.
"""

import datetime
import os
import re

from career_track_record import posting_file

MODES = ("demand", "coverage", "report")
CHOSEN = "chosen"
MUST_FIND = "must-find"
GAP_PERCENT = 30


class KeywordError(Exception):
    """The scan cannot run. The message is the one line for stderr."""


class Result(object):
    """What a run produced. See the module docstring."""

    def __init__(self, exit_code, ran, text="", error="", families=None):
        self.exit_code = exit_code
        self.ran = ran
        self.text = text
        self.error = error
        self.families = families if families is not None else []

    def __repr__(self):
        return "Result(exit_code=%r, ran=%r, error=%r)" % (
            self.exit_code, self.ran, self.error)


def _one_line(message):
    return " ".join(message.replace("\r", "\n").split("\n"))


def _failure(message):
    return Result(2, False, text="", error=_one_line("cannot run: " + message))


# ---------------------------------------------------------------- terms

def _read_utf8(path, what):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise KeywordError("%s cannot be read: %s" % (what, exc.strerror or exc))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise KeywordError("%s is not valid UTF-8: %s" % (what, path))


def _compile(pattern):
    try:
        return re.compile(pattern, re.IGNORECASE)
    except Exception as exc:
        raise KeywordError(
            "term pattern is not a valid regular expression: %s (%s)" % (pattern, exc)
        )


def load_terms(path):
    """Read a term table into a list of (family, pattern, note) tuples.

    Raises KeywordError for spec section 8 cases 5, 8 and 9.
    """
    if not os.path.isfile(path):
        raise KeywordError("term table is missing: %s" % path)
    text = _read_utf8(path, "term table")
    rows = []
    lines = text.split("\n")
    for number, line in enumerate(lines[1:], start=2):
        if line.endswith("\r"):
            line = line[:-1]
        if line == "":
            continue
        cells = line.split("\t")
        family = cells[0]
        pattern = cells[1] if len(cells) > 1 else ""
        note = cells[2] if len(cells) > 2 else ""
        if family == "" or pattern == "":
            raise KeywordError(
                "term table line %d needs a family and a pattern" % number
            )
        rows.append((family, pattern, note))
    if not rows:
        raise KeywordError("term table has no rows: %s" % path)
    for _family, pattern, _note in rows:
        _compile(pattern)
    return rows


def _build_families(terms):
    """Return an ordered list of family dicts, each with its variants."""
    if not terms:
        raise KeywordError("term table has no rows")
    order = []
    by_name = {}
    for row_index, row in enumerate(terms):
        family, pattern, note = row
        entry = by_name.get(family)
        if entry is None:
            entry = {"family": family, "chosen": False, "must_find": False,
                     "variants": []}
            by_name[family] = entry
            order.append(entry)
        if note == CHOSEN:
            entry["chosen"] = True
        if note == MUST_FIND:
            entry["must_find"] = True
        entry["variants"].append(
            {"row": row_index, "pattern": pattern, "regex": _compile(pattern)}
        )
    return order


# ---------------------------------------------------------------- copy files

_NOTE_RE = re.compile(
    r"""(?<!\w)note\s*:\s*(?:"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`[^`]*`)""",
    re.DOTALL,
)
_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE_RE = re.compile(r"^[^\S\n]*//[^\n]*(?:\n|\Z)", re.MULTILINE)


def clean_typescript(text):
    """Apply the three cleanings of spec 4.5, in order."""
    text = _NOTE_RE.sub("note: ''", text)
    text = _BLOCK_RE.sub("", text)
    return _COMMENT_LINE_RE.sub("", text)


def _normalise_path(path):
    expanded = os.path.expanduser(path)
    parts = [part for part in expanded.split("/") if part not in ("", ".")]
    joined = "/".join(parts)
    if expanded.startswith("/"):
        joined = "/" + joined
    return joined or "."


def _label_copies(paths):
    """Dedupe typed paths, then label them (spec 12, decision 6).

    Returns a list of (normalised path, label) in first-seen order.
    """
    seen = []
    for path in paths:
        norm = _normalise_path(path)
        if norm not in seen:
            seen.append(norm)
    groups = {}
    for norm in seen:
        groups.setdefault(norm.split("/")[-1], []).append(norm)
    labels = {}
    for base, members in groups.items():
        if len(members) == 1:
            labels[members[0]] = base
            continue
        split = {m: [p for p in m.split("/") if p] for m in members}
        deepest = max(len(parts) for parts in split.values())
        chosen = None
        for k in range(1, deepest + 1):
            candidate = {m: "/".join(split[m][-k:]) for m in members}
            if len(set(candidate.values())) == len(members):
                chosen = candidate
                break
        if chosen is None:
            chosen = {m: m for m in members}
        labels.update(chosen)
    return [(norm, labels[norm]) for norm in seen]


def _read_copy(norm, keep_notes):
    if not os.path.isfile(norm):
        raise KeywordError("copy file does not exist: %s" % norm)
    text = _read_utf8(norm, "copy file")
    if norm.split("/")[-1].endswith(".ts") and not keep_notes:
        text = clean_typescript(text)
    return text


# ---------------------------------------------------------------- postings

def _list_postings(folder):
    if folder is None or not os.path.isdir(folder):
        raise KeywordError("postings folder has no .txt files: %s" % folder)
    names = sorted(
        name for name in os.listdir(folder)
        if name.endswith(".txt") and os.path.isfile(os.path.join(folder, name))
    )
    if not names:
        raise KeywordError("postings folder has no .txt files: %s" % folder)
    return [os.path.join(folder, name) for name in names]


def _read_postings(folder):
    postings = []
    for path in _list_postings(folder):
        try:
            postings.append(posting_file.read_posting(path))
        except posting_file.PostingError as exc:
            raise KeywordError(exc.message)
        except OSError as exc:
            raise KeywordError("%s cannot be read: %s" % (path, exc.strerror or exc))
    return postings


# ---------------------------------------------------------------- counting

def _count(regex, text):
    return sum(1 for _ in regex.finditer(text))


def percent(demand, total):
    """demand/total as a whole percent, exact, halves to the even neighbour."""
    quotient, remainder = divmod(demand * 100, total)
    twice = remainder * 2
    if twice > total or (twice == total and quotient % 2 == 1):
        quotient += 1
    return quotient


def _is_gap(demand, total, copy_hits):
    return demand * 100 >= GAP_PERCENT * total and copy_hits == 0


def _escape_cell_pattern(pattern):
    return pattern.replace("|", "\\|")


def _table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _scan_postings(families, postings):
    """Fill in demand, hits and variant counts for each family."""
    for entry in families:
        entry["demand"] = 0
        entry["hits"] = 0
        for variant in entry["variants"]:
            variant["hits"] = 0
            variant["first"] = None
        for index, posting in enumerate(postings):
            family_hits = 0
            for variant in entry["variants"]:
                count = _count(variant["regex"], posting.body)
                if count and variant["first"] is None:
                    variant["first"] = index
                variant["hits"] += count
                family_hits += count
            entry["hits"] += family_hits
            if family_hits:
                entry["demand"] += 1


def _check_must_find(families):
    marked = [e for e in families if e["must_find"]]
    if not marked:
        raise KeywordError("no family in the term table is marked must-find")
    if all(e["demand"] == 0 for e in marked):
        raise KeywordError(
            "every must-find family has zero demand: the run does not see the postings"
        )


def _top_variants(entry):
    hit = [v for v in entry["variants"] if v["hits"] > 0]
    hit.sort(key=lambda v: (-v["hits"], v["first"], v["row"]))
    if not hit:
        return "-"
    return ", ".join(
        "`%s` (%d)" % (_escape_cell_pattern(v["pattern"]), v["hits"]) for v in hit[:3]
    )


def run(mode, *, terms, postings=None, copy=(), keep_notes=False, today=None):
    """Run one mode and return a Result."""
    try:
        return _run(mode, terms, postings, copy, keep_notes, today)
    except KeywordError as exc:
        return _failure(str(exc))
    except (posting_file.PostingError, OSError) as exc:
        return _failure(str(getattr(exc, "message", exc)))


def _run(mode, terms, postings_dir, copy, keep_notes, today):
    if mode not in MODES:
        raise KeywordError("unknown mode: %s" % mode)
    families = _build_families(list(terms))
    labelled = []
    texts = []
    if mode in ("coverage", "report"):
        labelled = _label_copies(list(copy))
        for norm, _label in labelled:
            if not os.path.isfile(norm):
                raise KeywordError("copy file does not exist: %s" % norm)
    postings = []
    if mode in ("demand", "report"):
        postings = _read_postings(postings_dir)
    for norm, _label in labelled:
        texts.append(_read_copy(norm, keep_notes))
    labels = [label for _norm, label in labelled]

    for entry in families:
        entry["copy"] = {}
        for label, text in zip(labels, texts):
            entry["copy"][label] = sum(
                _count(v["regex"], text) for v in entry["variants"]
            )

    if mode == "coverage":
        return _coverage(families, labels)
    _scan_postings(families, postings)
    _check_must_find(families)
    total = len(postings)
    if mode == "demand":
        return _demand(families, total, today)
    return _report(families, labels, total)


def _row(entry, mode, demand=None, pct=None, gap=None, hits=None, copy=None):
    return {
        "family": entry["family"],
        "chosen": entry["chosen"],
        "demand": demand,
        "percent": pct,
        "hits": hits,
        "copy": copy if copy is not None else {},
        "gap": gap,
    }


def _coverage(families, labels):
    rows = []
    records = []
    for entry in families:
        rows.append([entry["family"]] + [str(entry["copy"][l]) for l in labels])
        records.append(_row(entry, "coverage", copy=dict(entry["copy"])))
    text = _table(["family"] + labels, rows) + "\n"
    return Result(0, True, text=text, families=records)


def _demand(families, total, today):
    date = today if today is not None else datetime.date.today()
    ordered = sorted(families, key=lambda e: (-e["demand"], -e["hits"], e["family"]))
    rows = []
    records = []
    for entry in ordered:
        pct = percent(entry["demand"], total)
        rows.append([
            entry["family"],
            "%d/%d" % (entry["demand"], total),
            "%d%%" % pct,
            str(entry["hits"]),
            _top_variants(entry),
        ])
        records.append(_row(entry, "demand", demand=entry["demand"], pct=pct,
                            hits=entry["hits"]))
    heading = "# Demand, %s (%d postings)" % (date.isoformat(), total)
    table = _table(["family", "postings", "%", "hits", "top variants"], rows)
    text = heading + "\n\n" + table + "\n\n"
    return Result(0, True, text=text, families=records)


def _report(families, labels, total):
    ordered = sorted(families, key=lambda e: (-e["demand"], e["family"]))
    rows = []
    records = []
    gaps = []
    for entry in ordered:
        pct = percent(entry["demand"], total)
        copy_hits = sum(entry["copy"].values())
        gap = _is_gap(entry["demand"], total, copy_hits)
        name = entry["family"] + (" (chosen)" if entry["chosen"] else "")
        rows.append(
            [name, "%d/%d (%d%%)" % (entry["demand"], total, pct)]
            + [str(entry["copy"][l]) for l in labels]
            + ["GAP" if gap else ""]
        )
        records.append(_row(entry, "report", demand=entry["demand"], pct=pct,
                            hits=entry["hits"], gap=gap, copy=dict(entry["copy"])))
        if gap:
            gaps.append("%s (%d%% of postings, 0 in copy)" % (entry["family"], pct))
    table = _table(["family", "demand"] + labels + ["gap"], rows)
    summary = "Keywords: " + ("; ".join(gaps) if gaps else "none")
    return Result(0, True, text=table + "\n\n" + summary + "\n", families=records)
