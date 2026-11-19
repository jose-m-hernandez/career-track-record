"""``track-record setup``: choose your record folder.

Asks once where the record folder is (or takes it from --folder), refuses a folder git
tracks, makes the folder and its four layout folders, and writes a small config naming it.
It runs no check and writes nothing else. Output goes through the ``out`` and ``err``
functions the command line hands in, so output failures end as they do for every command."""

import os
import sys

from career_track_record import config, record_folder
from career_track_record.barred import printed_path

LAYOUT = (
    ("sources", "old résumés, letters and notes you collect here; no command looks here yet"),
    ("postings", "saved job postings; keywords looks here"),
    ("drafts", "your own document versions, kept here if you like; no command looks here yet"),
    ("plans", "frozen plans for ab and panel, kept here if you like; no command looks here "
              "yet"),
)
FILES = (
    ("barred-list.txt", "your barred wording list (barred)"),
    ("claims-list.txt", "your approved claims (claims)"),
    ("tone-rules.json", "your tone rules (tone; the shipped rules are used without it)"),
    ("terms.tsv", "your keyword terms (keywords)"),
)
NEXT = ('next: write barred-list.txt in your record folder, then run: track-record barred '
        '--control "Your Name" FILE; see docs/guides/barred.md')
OPTION_2_WARNING = ('Files in this folder stay private only while git ignores it. '
                    'Do not run "git add -f" or "git clean -x" on it, and a fresh clone '
                    'will not carry it.')
MAX_TRIES = 3
SHOWN = (("barred --list", "barred-list.txt"), ("claims --list", "claims-list.txt"),
         ("tone --rules", "tone-rules.json"), ("keywords --postings", "postings"),
         ("keywords --terms", "terms.tsv"))


class _Stop(Exception):
    """Setup ends with this exit code; the line (if any) is already written."""

    def __init__(self, code):
        Exception.__init__(self, code)
        self.code = code


def _is_terminal(stream):
    try:
        return stream is not None and stream.isatty()
    except (OSError, ValueError):
        return False


def absolute(path):
    """``~`` expanded, a relative path made absolute against the current directory."""
    return os.path.abspath(os.path.expanduser(path))


class _Session:
    def __init__(self, out, err, environ):
        self.out = out
        self.err = err
        self.environ = environ

    def refuse(self, code, text):
        self.err(text + "\n")
        raise _Stop(code)

    def ask(self, prompt):
        """Write the prompt and read one line; None at the end of input."""
        self.err(prompt)
        try:
            line = sys.stdin.readline()
        except (OSError, ValueError, UnicodeDecodeError):
            return None
        return line if line != "" else None


def show(out, err, environ=None):
    """``setup --show``: the seven fixed lines, reading only."""
    try:
        path, folder = config.read_config(environ)
    except config.ConfigError as exc:
        err(exc.line() + "\n")
        return 2
    if folder is None:
        out("config: %s (not found)\n" % printed_path(config.config_path(environ)))
        out("record folder: none\n")
        for label, _name in SHOWN:
            out("%s: none\n" % label)
        return 0
    lines = ["config: %s (found)" % printed_path(path),
             "record folder: %s (not checked)" % printed_path(folder)]
    for label, name in SHOWN:
        lines.append("%s: %s (not checked)"
                     % (label, printed_path(os.path.join(folder, name))))
    out("\n".join(lines) + "\n")
    return 0


def _choose(session):
    """The question: three choices, the first the default. Returns the chosen folder
    (absolute)."""
    try:
        here = os.getcwd()
    except OSError:
        session.refuse(2, "cannot run: setup: cannot read the current directory")
    default = os.path.join(os.path.expanduser("~"), "career-record")
    inside = os.path.join(here, "my-record")
    session.err("Where should your record folder be?\n"
                "  1. A folder outside any git repository (recommended: git pushes only "
                "files inside a repository): %s\n"
                "  2. A folder here, kept out of git (for people working inside a clone of "
                "this project): %s\n"
                "  3. Another folder: you type its path\n" % (printed_path(default),
                                                              printed_path(inside)))
    for _try in range(MAX_TRIES):
        answer = session.ask("Choice [1]: ")
        if answer is None:
            break
        answer = answer.strip()
        if answer in ("", "1"):
            return default
        if answer == "2":
            session.err(OPTION_2_WARNING + "\n")
            return inside
        if answer == "3":
            typed = session.ask("Path: ")
            if typed is None:
                break
            typed = typed.rstrip("\r\n")
            if typed.strip() != "":
                return absolute(typed)
        session.err("Not a choice.\n")
    session.refuse(2, "cannot run: setup: no valid answer")


def _keep_it(session, folder):
    """True to keep the folder the config names. False goes on to the question."""
    session.err("Record folder: %s\n" % printed_path(folder))
    for _try in range(MAX_TRIES):
        answer = session.ask("Keep it? [Y/n] ")
        if answer is None:
            break
        answer = answer.strip()
        if answer in ("", "Y", "y"):
            return True
        if answer in ("N", "n"):
            return False
        session.err("Not a choice.\n")
    session.refuse(2, "cannot run: setup: no valid answer")


def _check_folder(session, folder, asked):
    """Steps 3 and 4: it must not be a file, and git must not track it. ``asked`` is True
    when setup asked its question, which changes the end of a refusal's line."""
    try:
        exists = os.path.lexists(folder)
        is_folder = os.path.isdir(folder)
    except (OSError, ValueError):
        exists, is_folder = False, False
    if exists and not is_folder:
        session.refuse(2, "cannot run: setup: %s is not a folder" % printed_path(folder))
    refused = record_folder.refusal(record_folder.decide(folder), asked)
    if refused is not None:
        session.refuse(*refused)


def _make_folder(session, path, parents=False):
    """Create ``path`` with mode 0700 when it does not exist; an existing folder keeps its
    mode. Exits 2 naming ``path`` on any failure."""
    try:
        if os.path.isdir(path):
            return
        if parents:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        os.mkdir(path, 0o700)
        os.chmod(path, 0o700)
    except (OSError, ValueError):
        session.refuse(2, "cannot run: setup: cannot create %s" % printed_path(path))


def _create(session, folder):
    """The record folder, then the four layout folders in order."""
    _make_folder(session, folder, parents=True)
    for name, _meaning in LAYOUT:
        _make_folder(session, os.path.join(folder, name))


def run(folder_option, out, err, environ=None):
    """``setup`` and ``setup --folder PATH`` (``folder_option`` is the PATH or None).
    Returns the exit code."""
    session = _Session(out, err, environ)
    try:
        return _run(session, folder_option)
    except _Stop as stop:
        return stop.code


def _run(session, folder_option):
    asking = folder_option is None
    if asking and not (_is_terminal(sys.stdin) and _is_terminal(sys.stderr)):
        session.refuse(2, "cannot run: setup needs --folder when it is not run in a terminal")
    try:
        path, old = config.read_config(session.environ)
        invalid = None
    except config.ConfigError as exc:
        path, old, invalid = config.config_path(session.environ), None, exc
    if invalid is not None and asking:
        session.refuse(2, "cannot run: setup: the config is not valid (%s); give --folder to "
                          "replace it" % invalid.reason)
    if asking:
        if old is not None and _keep_it(session, old):
            folder = old
        else:
            folder = _choose(session)
    else:
        folder = absolute(folder_option)
    if "\0" in folder:
        session.refuse(2, "cannot run: setup: cannot create %s" % printed_path(folder))
    keep = old is not None and folder == old
    _check_folder(session, folder, asking)
    _create(session, folder)
    if not keep:
        try:
            config.write_config(folder, session.environ)
        except config.ConfigWriteError:
            session.refuse(2, "cannot run: setup: cannot write the config")
    lines = ["Setup done.", "config: %s" % printed_path(path),
             "record folder: %s" % printed_path(folder)]
    for name, meaning in LAYOUT:
        lines.append("  %-11s%s" % (name + "/", meaning))
    lines.append("Create these in your record folder when you need them; the commands look "
                 "for them there:")
    for name, meaning in FILES:
        lines.append("  %-18s%s" % (name, meaning))
    lines.append(NEXT)
    if old is not None and not keep:
        lines.append("The old folder is unchanged: %s" % printed_path(old))
    session.out("\n".join(lines) + "\n")
    return 0
