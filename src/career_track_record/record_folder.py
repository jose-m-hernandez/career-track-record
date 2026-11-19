"""Decide whether a folder may hold the record: is it tracked by git, or inside a work tree
that git does not ignore?

This is the only module that starts git, and it starts it in one place, ``_git``, called for
``ls-files`` and for ``check-ignore``. It only reads: it never creates, moves or deletes
anything, and the git commands it runs write nothing."""

import os
import subprocess

from career_track_record.barred import printed_path

ALLOWED = "allowed"
TRACKED = "tracked"
NOT_IGNORED = "not ignored"
CANNOT_TELL = "cannot tell"
GIT_TIMEOUT = 30

# Variables that point git at a repository other than the one around the folder asked about.
# They are dropped from git's environment; everything else is passed on unchanged.
GIT_LOCATION_VARIABLES = frozenset([
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM"])

# The end of a refusal's line depends on who asks: ``setup`` asked its question (the person
# can choose again), ``setup --folder`` or a write into the record folder (the person must
# change the folder or what git does with it).
ASKED_SUFFIX = "; re-run setup and choose 1"
TRACKED_SUFFIX = "; move the record folder out of git, or stop git tracking the files in it"
NOT_IGNORED_SUFFIX = "; move the record folder out of git, or have git ignore it"


class Verdict:
    """``kind`` is ALLOWED, TRACKED, NOT_IGNORED or CANNOT_TELL; ``folder`` is the folder as
    given, for the caller to name; ``reason`` is the git reason words for CANNOT_TELL."""

    def __init__(self, kind, folder, reason=""):
        self.kind = kind
        self.folder = folder
        self.reason = reason

    @property
    def allowed(self):
        return self.kind == ALLOWED

    def __repr__(self):
        return "Verdict(%r, %r, %r)" % (self.kind, self.folder, self.reason)


class _GitUnavailable(Exception):
    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


def _exists(path):
    try:
        return os.path.lexists(path)
    except (OSError, ValueError):
        return False


def resolve(path):
    """The nearest existing ancestor of ``path`` (or ``path`` itself), resolved with
    realpath so a symbolic link is seen for what it is, with the missing components
    appended. Also returns that ancestor."""
    missing = []
    here = path
    while not _exists(here):
        parent, name = os.path.split(here)
        if parent == here or name == "":
            break
        missing.append(name)
        here = parent
    ancestor = os.path.realpath(here)
    resolved = ancestor
    for name in reversed(missing):
        resolved = os.path.join(resolved, name)
    return resolved, ancestor


def _nearest_directory(path):
    here = path
    while not os.path.isdir(here):
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return here


def _work_tree_above(directory):
    here = directory
    while True:
        if _exists(os.path.join(here, ".git")):
            return True
        parent = os.path.dirname(here)
        if parent == here:
            return False
        here = parent


def scrubbed_environment():
    """A copy of this process's environment without the variables in GIT_LOCATION_VARIABLES."""
    return {name: value for name, value in os.environ.items()
            if name not in GIT_LOCATION_VARIABLES}


def _git(directory, *args):
    """Run git in ``directory`` and return (exit code, standard output bytes). Raises
    _GitUnavailable with reason words when git cannot be run."""
    try:
        done = subprocess.run(["git", "-C", directory, *args],
                              stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=GIT_TIMEOUT,
                              env=scrubbed_environment(), check=False)
    except FileNotFoundError:
        raise _GitUnavailable("git was not found")
    except subprocess.TimeoutExpired:
        raise _GitUnavailable("git did not answer in time")
    except (OSError, ValueError):
        raise _GitUnavailable("git could not be run")
    return done.returncode, done.stdout


def decide(folder):
    """The verdict for the absolute path ``folder``, which may not exist yet. No git program
    runs when no work tree is found above it; with a work tree, git failing to answer is
    CANNOT_TELL, so no answer means no folder."""
    resolved, ancestor = resolve(folder)
    start = _nearest_directory(ancestor)
    if not _work_tree_above(start):
        return Verdict(ALLOWED, folder)
    try:
        code, listing = _git(start, "--literal-pathspecs", "ls-files", "-z", "--", resolved)
        if code != 0:
            return Verdict(CANNOT_TELL, folder, "git ls-files exited %d" % code)
        if listing:
            return Verdict(TRACKED, folder)
        code, _out = _git(start, "check-ignore", "-q", "--", resolved + "/")
    except _GitUnavailable as exc:
        return Verdict(CANNOT_TELL, folder, exc.reason)
    if code == 0:
        return Verdict(ALLOWED, folder)
    if code == 1:
        return Verdict(NOT_IGNORED, folder)
    return Verdict(CANNOT_TELL, folder, "git check-ignore exited %d" % code)


def refusal(verdict, asked=False):
    """(exit code, one line) for a verdict that is not ALLOWED; None for an allowed folder.
    ``asked`` is True only for ``setup`` run without --folder, which ends the line with the
    suffix that tells the person to choose again. The folder is escaped as a printed path."""
    shown = printed_path(verdict.folder)
    if verdict.kind == TRACKED:
        return 1, ("refused: %s holds files git tracks; pick a folder git does not track%s"
                   % (shown, ASKED_SUFFIX if asked else TRACKED_SUFFIX))
    if verdict.kind == NOT_IGNORED:
        return 1, ("refused: %s is inside a git work tree and git does not ignore it%s"
                   % (shown, ASKED_SUFFIX if asked else NOT_IGNORED_SUFFIX))
    if verdict.kind == CANNOT_TELL:
        return 2, ("cannot run: cannot tell whether %s is tracked (%s)"
                   % (shown, verdict.reason))
    return None
