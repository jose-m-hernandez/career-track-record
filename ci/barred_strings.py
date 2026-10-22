"""Barred-strings scan.

Reads a private list of strings (one per line) and fails if any of them
appears in any version of any file reachable from HEAD (contents and file
names, each blob and each path once), in a commit message, in an author or
committer name or email, or in the branch name of a repository.

Matching ignores case, Unicode compatibility forms, invisible format
characters (Unicode category Cf) and the length of whitespace runs.

It never prints a matched string, only the entry's number. It proves the
matcher works on every run by finding a canary entry in a temp file first.

Exit status: 0 clean, 1 hit, 2 could not run.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

ENV_KEYS = (
    "BARRED_STRINGS",
    "BARRED_STRINGS_PATH",
    "GITHUB_ACTIONS",
    "GITHUB_EVENT_NAME",
    "GITHUB_EVENT_PATH",
    "GITHUB_REPOSITORY",
    "GITHUB_HEAD_REF",
    "GITHUB_REF_NAME",
)

CANARY_PREFIX = "barred-strings-canary-"
CANARY_MIN_TAIL = 8
USAGE = "usage: barred_strings.py [--repo PATH]"

MSG_FORK = (
    "barred-strings scan: pull request from a fork: secrets are not available "
    "here, so the scan cannot run; failing closed"
)
MSG_NO_LIST = (
    "barred-strings scan: no list: set the BARRED_STRINGS secret (CI) or "
    "BARRED_STRINGS_PATH (local); failing closed"
)
MSG_FILE_IN_CI = (
    "barred-strings scan: BARRED_STRINGS_PATH is not accepted in CI; failing closed"
)
MSG_BOTH = (
    "barred-strings scan: set BARRED_STRINGS or BARRED_STRINGS_PATH, not both; "
    "failing closed"
)
MSG_FILE_IN_REPO = (
    "barred-strings scan: the list file must live outside the repository; "
    "failing closed"
)
MSG_FILE_UNREADABLE = (
    "barred-strings scan: cannot read the list file; failing closed"
)
MSG_NOT_CANARY = (
    "barred-strings scan: entry 1 is not a canary (barred-strings-canary- plus at "
    "least 8 letters or digits); failing closed"
)
MSG_SELF_TEST = (
    "barred-strings scan: self-test failed: the matcher did not find the "
    "canary; failing closed"
)
MSG_CANARY_FLAG = (
    "barred-strings scan: entry 1 (the canary) cannot carry the word flag; "
    "failing closed"
)
MSG_LIST_MALFORMED_CI = (
    "barred-strings scan: the list is malformed; run the scan locally to see "
    "which entry; failing closed"
)
MSG_SHALLOW = (
    "barred-strings scan: repository is shallow; fetch full history "
    "(fetch-depth: 0); failing closed"
)
MSG_NO_HEAD = "barred-strings scan: no commit at HEAD; failing closed"
MSG_NO_BRANCH = (
    "barred-strings scan: cannot determine the branch name; failing closed"
)
MSG_SUBMODULE_CI = (
    "barred-strings scan: a submodule entry is in history; run the scan "
    "locally to see which; failing closed"
)
MSG_BLOB_NOT_UTF8_CI = (
    "barred-strings scan: a blob is not UTF-8 text; run the scan locally to "
    "see which; failing closed"
)
MSG_COMMIT_NOT_UTF8_CI = (
    "barred-strings scan: a commit is not UTF-8 text; run the scan locally "
    "to see which; failing closed"
)


class ListError(Exception):
    """The list is unusable. The message is safe to print."""


class Failure(Exception):
    """A run that cannot proceed. The message is safe to print."""


class StateFailure(Failure):
    """A repository state the scan cannot read. str() is the local message,
    which may name a SHA; ci_message is the one safe for a public log."""

    def __init__(self, local_message, ci_message):
        super().__init__(local_message)
        self.ci_message = ci_message


class GitError(Exception):
    """A git call failed. Carries no message on purpose."""


_WHITESPACE_RUN = re.compile(r"\s+")


def fold(text):
    """Fold for matching: NFKC and case, no format characters, one-space runs."""
    folded = unicodedata.normalize(
        "NFKC", unicodedata.normalize("NFKC", text).casefold()
    )
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")
    return _WHITESPACE_RUN.sub(" ", folded)


def is_canary(folded_entry):
    if not folded_entry.startswith(CANARY_PREFIX):
        return False
    tail = folded_entry[len(CANARY_PREFIX):]
    if len(tail) < CANARY_MIN_TAIL:
        return False
    return all(("a" <= ch <= "z") or ("0" <= ch <= "9") for ch in tail)


def parse_entries(text):
    """Return (entry, word_flag) pairs.

    An entry ends at the first tab. If the text after that tab, up to the next
    tab, is exactly "word" in any case, the entry matches only as a whole word.
    Any other text after the first tab is a note.
    """
    pairs = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = line.split("\t")
        word = len(fields) > 1 and fields[1].casefold() == "word"
        pairs.append((fields[0].strip(), word))
    if not pairs:
        raise ListError(MSG_NO_LIST)
    for ordinal, (entry, _) in enumerate(pairs, 1):
        if fold(entry) == "":
            raise ListError(
                "barred-strings scan: entry %d is empty after normalisation; "
                "failing closed" % ordinal
            )
    if not is_canary(fold(pairs[0][0])):
        raise ListError(MSG_NOT_CANARY)
    if pairs[0][1]:
        raise ListError(MSG_CANARY_FLAG)
    return pairs


def parse_list(text):
    """Return the entries. An entry ends at the first tab; the rest is a note."""
    return [entry for entry, _ in parse_entries(text)]


def is_boundary_char(ch):
    """False for letters and decimal digits, True for everything else."""
    category = unicodedata.category(ch)
    return not (category.startswith("L") or category == "Nd")


def _word_match(folded_text, entry):
    start = folded_text.find(entry)
    while start != -1:
        end = start + len(entry)
        if (start == 0 or is_boundary_char(folded_text[start - 1])) and (
            end == len(folded_text) or is_boundary_char(folded_text[end])
        ):
            return True
        start = folded_text.find(entry, start + 1)
    return False


def find_hits(text, folded_entries, word_flags=None):
    folded_text = fold(text)
    if word_flags is None:
        word_flags = [False] * len(folded_entries)
    hits = []
    for ordinal, (entry, word) in enumerate(zip(folded_entries, word_flags), 1):
        if word:
            if _word_match(folded_text, entry):
                hits.append(ordinal)
        elif entry in folded_text:
            hits.append(ordinal)
    return hits


def printable(text):
    """Escape control characters so a name cannot forge an output line."""
    out = []
    for ch in text:
        if unicodedata.category(ch) in ("Cc", "Cs"):
            out.append("\\x%02x" % ord(ch) if ord(ch) < 256 else "\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def _git(repo, args, data=None, check=True):
    proc = subprocess.run(
        ["git", "-C", repo] + list(args),
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise GitError()
    return proc


def _inside(path, top):
    path = os.path.realpath(path)
    top = os.path.realpath(top)
    return path == top or path.startswith(top.rstrip(os.sep) + os.sep)


def _read_blobs(repo, shas):
    """Return {sha: bytes} for the given blob ids, via one cat-file --batch."""
    shas = sorted(set(shas))
    if not shas:
        return {}
    data = ("\n".join(shas) + "\n").encode("ascii")
    out = _git(repo, ["cat-file", "--batch"], data=data).stdout
    blobs = {}
    pos = 0
    for sha in shas:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split(b" ")
        if len(header) != 3 or header[0].decode("ascii") != sha:
            raise GitError()
        size = int(header[2])
        start = nl + 1
        blobs[sha] = out[start:start + size]
        pos = start + size + 1
    return blobs


def _tree_records(repo, commit):
    """Return (mode, blob id, path) for every entry in a commit's tree."""
    tree = _git(repo, ["ls-tree", "-r", "-z", "--full-tree", commit]).stdout
    records = []
    for raw in tree.split(b"\0"):
        if not raw:
            continue
        meta, _, raw_path = raw.partition(b"\t")
        mode, _, sha = meta.decode("ascii").split(" ")
        records.append((mode, sha, raw_path.decode("utf-8")))
    return records


def scan_repo(repo, folded_entries, branch, word_flags=None):
    """Return (hits, n_blobs, n_paths, n_commits).

    Every blob and every path in every commit reachable from HEAD is scanned,
    each once. hits is a list of (kind, printed_location, ordinal); kind 0 is
    a blob or file name, 1 a commit, 2 the branch.
    """
    if _git(repo, ["rev-parse", "--is-shallow-repository"]).stdout.strip() == b"true":
        raise Failure(MSG_SHALLOW)
    if _git(
        repo, ["rev-parse", "--verify", "-q", "HEAD^{commit}"], check=False
    ).returncode != 0:
        raise Failure(MSG_NO_HEAD)

    hits = set()

    shas = _git(repo, ["rev-list", "--reverse", "HEAD"]).stdout.decode("ascii").split()

    # blob id -> (first commit, paths holding it in that commit)
    blob_first = {}
    # path -> first commit
    path_first = {}
    for commit in shas:
        in_commit = {}
        for mode, sha, path in _tree_records(repo, commit):
            if mode == "160000":
                raise StateFailure(
                    "barred-strings scan: a submodule entry first seen in %s; "
                    "failing closed" % commit[:12],
                    MSG_SUBMODULE_CI,
                )
            if path not in path_first:
                path_first[path] = commit
            in_commit.setdefault(sha, set()).add(path)
        for sha, paths in in_commit.items():
            if sha not in blob_first:
                blob_first[sha] = (commit, sorted(paths))

    path_hit = {}
    for path, commit in path_first.items():
        found = find_hits(path, folded_entries, word_flags)
        path_hit[path] = bool(found)
        for ordinal in found:
            hits.add((0, "a file name (first seen in %s)" % commit[:12], ordinal))

    blobs = _read_blobs(repo, list(blob_first))
    for sha, (commit, paths) in blob_first.items():
        try:
            text = blobs[sha].decode("utf-8")
        except UnicodeDecodeError:
            raise StateFailure(
                "barred-strings scan: blob %s (first seen in %s) is not UTF-8 "
                "text; failing closed" % (sha[:12], commit[:12]),
                MSG_BLOB_NOT_UTF8_CI,
            )
        found = find_hits(text, folded_entries, word_flags)
        if not found:
            continue
        shown = [path for path in paths if not path_hit[path]]
        if shown:
            first = "at " + printable(shown[0])
        else:
            first = "at a withheld path"
        where = "blob %s (first seen %s in %s)" % (sha[:12], first, commit[:12])
        for ordinal in found:
            hits.add((0, where, ordinal))

    log = _git(
        repo,
        ["log", "-z", "--no-mailmap", "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B", "HEAD"],
    ).stdout
    fields = log.split(b"\0")
    if fields and fields[-1].strip() == b"":
        fields.pop()
    if len(fields) != 6 * len(shas):
        raise GitError()
    newest_first = _git(repo, ["rev-list", "HEAD"]).stdout.decode("ascii").split()
    if sorted(newest_first) != sorted(shas):
        raise GitError()
    commit_order = {}
    for index, sha in enumerate(newest_first):
        got, author, author_email, committer, committer_email, message = fields[
            6 * index:6 * index + 6
        ]
        if got.decode("ascii").strip() != sha:
            raise GitError()
        commit_order[sha] = index
        try:
            parts = [
                part.decode("utf-8")
                for part in (
                    message, author, author_email, committer, committer_email
                )
            ]
        except UnicodeDecodeError:
            raise StateFailure(
                "barred-strings scan: commit %s is not UTF-8 text; "
                "failing closed" % sha,
                MSG_COMMIT_NOT_UTF8_CI,
            )
        for part in parts:
            for ordinal in find_hits(part, folded_entries, word_flags):
                hits.add((1, "commit " + sha, ordinal))

    for ordinal in find_hits(branch, folded_entries, word_flags):
        hits.add((2, "branch", ordinal))

    def order(hit):
        kind, where, ordinal = hit
        if kind == 1:
            return (kind, commit_order[where[len("commit "):]], ordinal, "")
        if kind == 0:
            return (kind, 0, ordinal, where)
        return (kind, 0, ordinal, "")

    return sorted(hits, key=order), len(blob_first), len(path_first), len(shas)


def _toplevel(repo):
    out = _git(repo, ["rev-parse", "--show-toplevel"]).stdout
    return out.decode("utf-8").rstrip("\n")


def _check_fork(environ):
    if environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return
    with open(environ.get("GITHUB_EVENT_PATH"), encoding="utf-8") as handle:
        event = json.load(handle)
    pull = event.get("pull_request") or {}
    head_repo = (pull.get("head") or {}).get("repo")
    if not head_repo or head_repo.get("full_name") != environ.get("GITHUB_REPOSITORY"):
        raise Failure(MSG_FORK)


def _get_list(environ, ci_mode, top):
    from_file = environ.get("BARRED_STRINGS_PATH") or ""
    from_env = environ.get("BARRED_STRINGS") or ""
    if ci_mode:
        if from_file:
            raise Failure(MSG_FILE_IN_CI)
        text = from_env
    else:
        if from_file and from_env:
            raise Failure(MSG_BOTH)
        if from_file:
            if _inside(from_file, top):
                raise Failure(MSG_FILE_IN_REPO)
            try:
                with open(from_file, encoding="utf-8") as handle:
                    text = handle.read()
            except (OSError, UnicodeDecodeError):
                raise Failure(MSG_FILE_UNREADABLE)
        else:
            text = from_env
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.strip():
        raise Failure(MSG_NO_LIST)
    return parse_entries(text)


def _self_test(entries, folded, top):
    fd, path = tempfile.mkstemp()
    try:
        if _inside(path, top):
            raise Failure(MSG_SELF_TEST)
        with os.fdopen(fd, "wb") as handle:
            handle.write(("self-test line: " + entries[0] + "\n").encode("utf-8"))
        with open(path, "rb") as handle:
            back = handle.read().decode("utf-8")
        if 1 not in find_hits(back, folded):
            raise Failure(MSG_SELF_TEST)
        c = folded[0]
        if 1 not in find_hits("self-test line: " + c + "\n", [c], [True]):
            raise Failure(MSG_SELF_TEST)
        if 1 in find_hits("x" + c + "x", [c], [True]):
            raise Failure(MSG_SELF_TEST)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _branch_name(environ, ci_mode, repo):
    if ci_mode:
        if environ.get("GITHUB_EVENT_NAME") == "pull_request":
            name = environ.get("GITHUB_HEAD_REF") or ""
        else:
            name = environ.get("GITHUB_REF_NAME") or ""
    else:
        proc = _git(repo, ["symbolic-ref", "--short", "-q", "HEAD"], check=False)
        name = proc.stdout.decode("utf-8").strip() if proc.returncode == 0 else ""
    if not name:
        raise Failure(MSG_NO_BRANCH)
    return name


def _run(argv, environ):
    repo = "."
    if argv == []:
        pass
    elif len(argv) == 2 and argv[0] == "--repo":
        repo = argv[1]
    else:
        print(USAGE, file=sys.stderr)
        return 2

    ci_mode = environ.get("GITHUB_ACTIONS") == "true"
    top = _toplevel(repo)
    if ci_mode:
        _check_fork(environ)
    try:
        pairs = _get_list(environ, ci_mode, top)
    except ListError as err:
        if ci_mode and str(err) != MSG_NO_LIST:
            raise ListError(MSG_LIST_MALFORMED_CI)
        raise
    entries = [entry for entry, _ in pairs]
    word_flags = [word for _, word in pairs]
    folded = [fold(entry) for entry in entries]
    _self_test(entries, folded, top)
    branch = _branch_name(environ, ci_mode, repo)

    try:
        hits, n_blobs, n_paths, n_commits = scan_repo(
            repo, folded, branch, word_flags
        )
    except StateFailure as err:
        if ci_mode:
            raise Failure(err.ci_message)
        raise
    if not ci_mode:
        for kind, where, ordinal in hits:
            print("entry %d matched in %s" % (ordinal, where))
    if hits:
        print("barred-strings scan: %d hit(s); failing" % len(hits))
        return 1
    print(
        "barred-strings scan: clean (%d entries; %d blobs; %d paths; "
        "%d commits; branch checked)"
        % (len(entries), n_blobs, n_paths, n_commits)
    )
    return 0


def main(argv, environ):
    try:
        return _run(argv, environ)
    except (Failure, ListError) as err:
        print(str(err), file=sys.stderr)
        return 2
    except Exception as err:
        print(
            "barred-strings scan: internal error (%s); failing closed"
            % type(err).__name__,
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
