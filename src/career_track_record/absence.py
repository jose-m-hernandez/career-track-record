"""Absence search: show that listed terms appear nowhere in a set of files.

The behaviour is stated in docs/specs/absence.md. In short: one declaration file names the
list, the files to search, the place where the fact would live, a control phrase that must be
found there, and the exclusions. Every file found is accounted for (read, excluded,
unreadable, or a link not followed), and a run is DEAD when the search could not see.

Folding and matching are barred's own: this module imports them from ``barred`` and copies
none of them, so one list means the same to both commands (spec section 8.1).

Nothing here prints a term, matched text, the control phrase, an exclusion's reason, the
list's path or a path whose name matches an entry.
"""

import hashlib
import os
import stat

from career_track_record import barred, reader_harness, record_check

_SCALAR_KEYS = ("label", "list", "place", "control")
_LIST_KEYS = ("search", "exclusions")
_REQUIRED = ("label", "search", "place", "control")
_BOM = b"\xef\xbb\xbf"
_NO_LIST = "no list (give --list or set BARRED_STRINGS_PATH)"


def _cannot(*lines):
    return barred.Result(2, False, text="",
                         error="\n".join("cannot run: " + line for line in lines))


# ---------------------------------------------------------------- the declaration

class _State(reader_harness.ParseState):
    """A parse state whose problems say ``declaration line``. A message never repeats text the
    declaration wrote as a key, which could be a term or the control phrase."""

    def __init__(self):
        reader_harness.ParseState.__init__(self)
        self.numbered = []

    def bad(self, number, message):
        if message.startswith("unknown key "):
            message = "unknown key"
        self.numbered.append((number, "declaration line %d: %s" % (number, message)))


class _Declaration(object):
    def __init__(self):
        self.label = None
        self.list = None
        self.place = None
        self.control = None
        self.search = []
        self.exclusions = []


def _norm(path):
    """The path with ``.`` and ``..`` resolved and nothing else: no link is followed."""
    return os.path.abspath(path)


def _through_link(base, written):
    """True when a component of ``written`` is a symbolic link. The components are walked as
    written, from ``base`` for a relative path and from the root for an absolute one, each
    checked with lstat; no link is followed or resolved to decide (spec section 3.3). A
    component that does not exist ends the walk: nothing below it can be a link."""
    here = os.sep if os.path.isabs(written) else base
    for part in written.split(os.sep):
        if part in ("", "."):
            continue
        here = os.path.join(here, part)
        try:
            if stat.S_ISLNK(os.lstat(here).st_mode):
                return True
        except OSError:
            return False
    return False


def _inside(key, container):
    """True when ``key`` is ``container`` or lies under it (both normalised)."""
    if key == container:
        return True
    prefix = container if container.endswith(os.sep) else container + os.sep
    return key.startswith(prefix)


def _search_folders(items, base):
    keys = []
    for item in items:
        full = os.path.join(base, item)
        if not _through_link(base, item) and os.path.isdir(full):
            keys.append(_norm(full))
    return keys


def _in_set(key, item_keys, folder_keys):
    return key in item_keys or any(_inside(key, folder) for folder in folder_keys)


def _parse_declaration(text, base):
    """(Declaration, problem lines). A declaration with problems cannot be run."""
    state = _State()
    scalars, lists = reader_harness.structure(state, text, _LIST_KEYS, _SCALAR_KEYS)
    decl = _Declaration()
    if "label" in scalars:
        number, value = scalars["label"]
        if reader_harness.NAME.match(value):
            decl.label = value
        else:
            state.bad(number, "the label holds letters, digits and - only")
    if "list" in scalars:
        decl.list = scalars["list"][1]
    if "place" in scalars:
        decl.place = scalars["place"][1]
    if "control" in scalars:
        decl.control = scalars["control"][1]
    for number, item in lists.get("search", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) != 1:
            state.bad(number, "a search item is one path")
            continue
        decl.search.append(parts[0])
    item_keys = [_norm(os.path.join(base, item)) for item in decl.search]
    folder_keys = _search_folders(decl.search, base)
    for number, item in lists.get("exclusions", []):
        parts = state.fields(number, item)
        if parts is None:
            continue
        if len(parts) < 2:
            state.bad(number, "an exclusion has no reason")
            continue
        if len(parts) > 2:
            state.bad(number, "an exclusion is written: path | reason")
            continue
        if not _in_set(_norm(os.path.join(base, parts[0])), item_keys, folder_keys):
            state.bad(number, "an exclusion is not inside the search set")
            continue
        decl.exclusions.append(parts[0])
    problems = [line for _n, line in sorted(state.numbered, key=lambda p: p[0])]
    for key in _REQUIRED:
        if key == "search":
            missing = "search" not in lists or not lists["search"]
        else:
            missing = key not in scalars
        if missing:
            problems.append("the declaration has no %s" % key)
    return decl, problems


# ---------------------------------------------------------------- the search set

class _Found(object):
    """One path found: a file or a symbolic link."""

    def __init__(self, written, opened, link):
        self.written = written
        self.opened = opened
        self.key = _norm(opened)
        self.link = link
        self.names = set()
        self.is_list = False
        self.status = None      # "link", "read", "excluded" or "unreadable"
        self.readable = False
        self.counts = {}        # entry number -> count in the text
        self.has_control = False
        self.in_exclusion = False

    def entries(self):
        return set(self.counts) | self.names

    def total(self):
        return sum(self.counts.values()) + len(self.names)


def _walk(top):
    """The paths under a folder, as (path inside it, kind), kind "link" or "file". Returns
    None when the folder cannot be listed. A folder met on the way that cannot be listed is
    itself reported as a "file", which the read then finds unreadable."""
    found = []
    stack = [(top, "")]
    while stack:
        folder, prefix = stack.pop()
        try:
            with os.scandir(folder) as entries:
                listed = list(entries)
        except OSError:
            if folder == top:
                return None
            found.append((prefix[:-1], "file"))
            continue
        for entry in listed:
            rel = prefix + entry.name
            try:
                if entry.is_symlink():
                    found.append((rel, "link"))
                    continue
                is_folder = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_folder = False
            if is_folder:
                stack.append((entry.path, rel + "/"))
            else:
                found.append((rel, "file"))
    return found


def _collect(items, base):
    """Every path found, in the order of the spec's section 3.3, each once."""
    out = []
    seen = set()

    def add(written, opened, link):
        path = _Found(written, opened, link)
        if path.key not in seen:
            seen.add(path.key)
            out.append(path)

    for item in items:
        full = os.path.join(base, item)
        if _through_link(base, item):
            add(item, full, True)
            continue
        if os.path.isdir(full):
            inside = _walk(full)
            if inside is None:
                add(item, full, False)
                continue
            for rel, kind in sorted(inside):
                add(item + "/" + rel, os.path.join(full, rel), kind == "link")
            continue
        add(item, full, False)
    return out


def _read_forms(opened):
    """(forms, soft-hyphen-rule forms) of a file, as ``barred`` reads it, or None when the
    file cannot be read."""
    try:
        if not stat.S_ISREG(os.stat(opened).st_mode):
            return None
        text = barred._read_text(opened, False)
        forms = barred._forms(text)
        if opened.lower().endswith(".pdf"):
            layout = barred._read_layout_text(opened)
            extra = barred._forms(barred._line_end_soft_hyphens(layout))
        else:
            extra = barred._forms(barred._line_end_soft_hyphens(text))
        return forms, extra
    except Exception:
        return None


def _count(entry, forms, extra):
    return max(barred._match(entry, forms)[0], barred._match(entry, extra)[0])


def _section6(path):
    return barred.printed_path(path).replace(",", "\\x2c")


def _name_entries(path, entries):
    """The numbers of the entries that match a path's name: as written, as barred prints it,
    and as this command prints it (spec section 4)."""
    numbers = set()
    for form in (path, barred.printed_path(path), _section6(path)):
        numbers |= set(e.number for e in barred._name_hits(form, entries))
    return numbers


def _buckets(found):
    """(read, excluded, unreadable, links) of the paths found, counted from their status."""
    counts = {"read": 0, "excluded": 0, "unreadable": 0, "link": 0}
    for path in found:
        counts[path.status] += 1
    return counts["read"], counts["excluded"], counts["unreadable"], counts["link"]


# ---------------------------------------------------------------- the run

def run(declaration, environ=None):
    """Run the absence search on one declaration file. Never raises."""
    try:
        return _run(declaration, os.environ if environ is None else environ)
    except Exception:
        return _cannot("internal error")


def _shown(path, position):
    if path.names or path.is_list:
        return "file #%d" % position
    return _section6(path.written)


def _run(declaration, environ):
    data, code = record_check.read_source(declaration)
    if code is not None:
        return _cannot("cannot read the declaration")
    digest = hashlib.sha256(data).hexdigest()
    if data.startswith(_BOM):
        data = data[len(_BOM):]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _cannot("the declaration is not valid UTF-8")
    base = os.path.dirname(declaration)
    decl, problems = _parse_declaration(text, base)
    if problems:
        return _cannot(*problems)

    list_path = os.path.join(base, decl.list) if decl.list is not None else None
    if list_path is None:
        list_path = environ.get("BARRED_STRINGS_PATH") or None
    if list_path is None:
        return _cannot(_NO_LIST)
    try:
        entries = barred.load_list(list_path)
    except barred.ListError as exc:
        return _cannot(str(exc))

    prepared = barred.prepare(decl.control)
    if prepared == "":
        return _cannot("the control phrase is empty")
    control = barred.Entry(0, prepared, False)
    control_forms = barred._forms(prepared)
    for entry in entries:
        if barred._match(entry, control_forms)[0] > 0:
            return _cannot("entry #%d matches the control phrase" % entry.number)
    label_hits = sorted(barred._name_hits(decl.label, entries), key=lambda e: e.number)
    if label_hits:
        return _cannot("the label matches entry #%d" % label_hits[0].number)

    item_keys = [_norm(os.path.join(base, item)) for item in decl.search]
    folder_keys = _search_folders(decl.search, base)
    exclusion_keys = [_norm(os.path.join(base, item)) for item in decl.exclusions]
    place_key = _norm(os.path.join(base, decl.place))

    found = _collect(decl.search, base)
    for path in found:
        path.names = _name_entries(path.written, entries)
        path.is_list = barred._is_the_list(path.opened, list_path)
        excluded = any(_inside(path.key, key) for key in exclusion_keys)
        path.in_exclusion = excluded
        if path.link:
            path.status = "link"
            continue
        forms = _read_forms(path.opened)
        path.readable = forms is not None
        if forms is not None:
            for entry in entries:
                count = _count(entry, forms[0], forms[1])
                if count > 0:
                    path.counts[entry.number] = count
            path.has_control = _count(control, forms[0], forms[1]) > 0
        if excluded:
            path.status = "excluded"
        else:
            path.status = "read" if path.readable else "unreadable"
    read, excluded, unreadable, links = _buckets(found)
    total = len(found)
    if total != read + excluded + unreadable + links:
        return _cannot("the files do not reconcile: found %d, read %d, excluded %d, "
                       "unreadable %d, links not followed %d"
                       % (total, read, excluded, unreadable, links))
    reconciliation = ("files: found %d, read %d, excluded %d, unreadable %d, "
                      "links not followed %d" % (total, read, excluded, unreadable, links))
    first = "declaration sha256 " + digest

    reason = None
    if total - links == 0:
        reason = "no file in the search set"
    elif not _in_set(place_key, item_keys, folder_keys):
        reason = "the place is not in the search set"
    elif any(_inside(place_key, key) for key in exclusion_keys):
        reason = "the place is inside an exclusion"
    elif unreadable:
        reason = "%d unreadable files" % unreadable
    elif not any(p.status == "read" and p.has_control and _inside(p.key, place_key)
                 for p in found):
        reason = "control not found at the place"
    if reason is not None:
        closing = "DEAD   %s: %s" % (decl.label, reason)
        return barred.Result(2, True, text="".join(
            line + "\n" for line in (first, reconciliation, closing)))

    lines = [first]
    shown = []
    for position, item in enumerate(decl.exclusions, 1):
        key = exclusion_keys[position - 1]
        names = _name_entries(item, entries)
        is_list = barred._is_the_list(os.path.join(base, item), list_path)
        label = ("exclusion #%d" % position if names or is_list else _section6(item))
        shown.append(label)
        hits = files = not_read = 0
        for path in found:
            if not _inside(path.key, key):
                continue
            hits += path.total()
            if not path.link:
                files += 1
                if not path.readable:
                    not_read += 1
        lines.append("excluded %s: %d hits in %d files, %d not read"
                     % (label, hits, files, not_read))
    hit_total = 0
    with_hits = 0
    for position, path in enumerate(found, 1):
        counted = path.status == "read" or (path.link and not path.in_exclusion)
        if not counted or path.total() == 0:
            continue
        hit_total += path.total()
        with_hits += 1
        numbers = ", ".join("#%d" % n for n in sorted(path.entries()))
        lines.append("hit %s: %d hits, entries %s"
                     % (_shown(path, position), path.total(), numbers))
    lines.append(reconciliation)
    tail = "; excluding " + ", ".join(shown) if shown else ""
    if hit_total:
        lines.append("FOUND  %s: %d hits in %d files, %d with hits, %d links not followed, "
                     "control found%s" % (decl.label, hit_total, read, with_hits, links, tail))
        code = 1
    else:
        lines.append("CLEAN  %s: 0 hits in %d files, %d links not followed, control found%s"
                     % (decl.label, read, links, tail))
        code = 0
    return barred.Result(code, True, text="".join(line + "\n" for line in lines))
