"""Forced failures: flip each assertion of the tests in scope, one at a time, in a throwaway
copy of HEAD, and check that the test fails and that its failure prints nothing captured.

usage, from the repository root (a reviewer runs it by hand; CI does not):

    python3 ci/forced_failures.py [--python PATH]... [--marker TEXT]... [--keep]

What it does:
  - makes a copy of HEAD with `git archive HEAD` into a fresh temporary folder and works only
    there; it never writes in the repository; without --keep it removes the folder at the end,
    also on an error;
  - the scope is ci/hygiene.py's assert_scope: the modules and classes in scope whose module
    starts a child process, the only ones whose assertions the rule constrains; in each it finds every
    `self.assertTrue`, `self.assertFalse` and `self.assertEqual` call (the names in FLIP); it does
    not force the `self.assertRaises` and `self.fail` calls there (the names in NOT_FORCED), and
    counts them instead;
  - for each call, one at a time: writes the file with that call flipped (assertTrue and
    assertFalse swap; assertEqual becomes assertNotEqual), runs the test method that holds it
    (when the call sits in a helper method, every test method of that class and of the classes
    that inherit from it), saves the output, and restores the file;
  - the run gets an environment built from nothing: PATH, a TMPDIR whose name holds a marker,
    and one sentinel variable with an invented value; --python is repeatable (one run of the
    flipped copy per interpreter; the default is the interpreter running this script);
  - a row is clean when every run exited non-zero, printed a `FAIL:` line and no `ERROR:` line,
    and printed none of: the sentinel's value, the TMPDIR marker, any --marker text.
    Otherwise the row is BAD;
  - prints one row per assertion, then a line `no assertion flipped in: <path>` for each module
    in scope where it flipped nothing, then `not flipped: K (assertRaises and fail calls, which
    this script does not force)` with K summed over the scope (also when K is 0), and a last
    line `assertions forced: N; not clean: M`;
    exit 0 when M is 0 and every module in scope had an assertion flipped; 1 when M is above 0
    or a module in scope had nothing flipped; 2 when it could not run (not a git repository,
    `git archive` failed, or no assertion in scope that it can flip);
  - the output of a BAD row is never printed: with --keep it is written to a file in the kept
    folder, whose path is printed, because that output is exactly the text the check exists to
    keep out of records.

Known limits are written beside the nearest test, in tests/test_forced_failures.py.

Exit status: 0 every row clean and every module in scope had an assertion flipped; 1 a row is
not clean, or a module in scope had nothing flipped; 2 could not run (not a git repository,
`git archive` failed, or no assertion in scope)."""

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci import hygiene  # noqa: E402

SENTINEL_NAME = "CTR_FF_SENTINEL"
SENTINEL = "sentinel-zq81-invented-value"
FLIP = {"assertTrue": "assertFalse", "assertFalse": "assertTrue", "assertEqual": "assertNotEqual"}
NOT_FORCED = ("assertRaises", "fail")
TIMEOUT = 600


class Site(object):
    """One assertion call: the class and method that hold it and where its name sits."""

    def __init__(self, cls, fn, attr, lineno, end_col):
        self.cls = cls
        self.fn = fn
        self.attr = attr
        self.lineno = lineno
        self.end_col = end_col


def sites(tree, classes):
    """Every self.assertTrue, self.assertFalse and self.assertEqual call in the classes of a
    module tree (all classes when classes is None), in source order."""
    found = []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        if classes is not None and cls.name not in classes:
            continue
        for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            for sub in ast.walk(fn):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr in FLIP and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "self"):
                    found.append(Site(cls.name, fn.name, sub.func.attr,
                                      sub.func.end_lineno, sub.func.end_col_offset))
    return sorted(found, key=lambda s: (s.lineno, s.end_col))


def not_flipped(tree, classes):
    """The number of self.<name> calls, with <name> in NOT_FORCED, in the same classes and
    methods that sites() walks. They are counted, never forced."""
    count = 0
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        if classes is not None and cls.name not in classes:
            continue
        for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            for sub in ast.walk(fn):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr in NOT_FORCED and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "self"):
                    count += 1
    return count


def flip(source, site):
    """The source with the one call at site flipped. Offsets are UTF-8 bytes, as the syntax
    tree counts them."""
    lines = source.split("\n")
    raw = lines[site.lineno - 1].encode("utf-8")
    start = site.end_col - len(site.attr)
    if raw[start:site.end_col] != site.attr.encode("utf-8"):
        raise ValueError("the call is not where the syntax tree says: line %d" % site.lineno)
    lines[site.lineno - 1] = (raw[:start] + FLIP[site.attr].encode("utf-8")
                              + raw[site.end_col:]).decode("utf-8")
    return "\n".join(lines)


def test_ids(tree, module, cls_name, fn_name):
    """The test methods to run for a call in fn_name: itself when it is a test, else every test
    method of the class and of the classes that inherit from it."""
    if fn_name.startswith("test"):
        return ["%s.%s.%s" % (module, cls_name, fn_name)]
    out = []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        bases = [getattr(b, "id", "") for b in cls.bases]
        if cls.name == cls_name or cls_name in bases:
            out += ["%s.%s.%s" % (module, cls.name, f.name) for f in cls.body
                    if isinstance(f, ast.FunctionDef) and f.name.startswith("test")]
    return out


def judge(code, text, secrets):
    """Return (clean, kind, leaks): kind is FAIL, ERROR or none; leaks counts the secrets that
    the output holds."""
    has_fail = re.search(r"^FAIL: ", text, re.M) is not None
    has_error = re.search(r"^ERROR: ", text, re.M) is not None
    kind = "FAIL" if has_fail else ("ERROR" if has_error else "none")
    leaks = len([s for s in secrets if s and s in text])
    return (code != 0 and has_fail and not has_error and leaks == 0), kind, leaks


def read_bytes_text(path):
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def write_text(path, text):
    with open(path, "wb") as handle:
        handle.write(text.encode("utf-8"))


def run_once(python, ids, root, env):
    try:
        proc = subprocess.run([python, "-B", "-m", "unittest"] + ids, cwd=root, env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return 124, ""
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def force(root, scope, pythons, markers, work, bad_log=None):
    """Force every assertion in scope in the copy at root. scope is a list of (path relative to
    root, class names or None). work is a folder the run may write in. Returns a list of row
    dicts. The files are restored after each assertion, also on an error."""
    temp = tempfile.mkdtemp(prefix="ff-tmp-marker-", dir=work)
    secrets = [SENTINEL, os.path.basename(temp)] + list(markers)
    env = {"PATH": "/usr/bin:/bin", "TMPDIR": temp, SENTINEL_NAME: SENTINEL}
    rows = []
    for rel, classes in scope:
        path = os.path.join(root, rel)
        module = rel[:-3].replace(os.sep, ".")
        source = read_bytes_text(path)
        tree = ast.parse(source)
        for site in sites(tree, classes):
            ids = test_ids(tree, module, site.cls, site.fn)
            runs = []
            try:
                write_text(path, flip(source, site))
                for python in pythons:
                    if not ids:
                        runs.append((python, 0, ""))
                    else:
                        code, text = run_once(python, ids, root, env)
                        runs.append((python, code, text))
            finally:
                write_text(path, source)
            verdicts = [judge(code, text, secrets) for _, code, text in runs]
            ok = bool(ids) and all(v[0] for v in verdicts)
            rows.append({
                "ok": ok, "rel": rel, "lineno": site.lineno, "attr": site.attr,
                "where": "%s.%s" % (site.cls, site.fn),
                "detail": " ".join("%s exit=%d kind=%s leaks=%d" % (
                    os.path.basename(py), code, v[1], v[2])
                    for (py, code, _), v in zip(runs, verdicts)) if ids else "no test method found",
            })
            if not ok and bad_log is not None:
                bad_log.write("##### %s:%d %s\n" % (rel, site.lineno, site.attr))
                for py, code, text in runs:
                    bad_log.write("--- %s exit %d\n%s\n" % (py, code, text))
    return rows


def row_text(row):
    return "%s %s:%d %s (%s) %s" % ("ok " if row["ok"] else "BAD", row["rel"], row["lineno"],
                                    row["attr"], row["where"], row["detail"])


def totals(rows):
    return "assertions forced: %d; not clean: %d" % (
        len(rows), len([r for r in rows if not r["ok"]]))


def make_copy(repo, destination):
    """Copy HEAD of the repository at repo into destination. Returns an error text or None."""
    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo,
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    if probe.returncode != 0:
        return "not a git repository"
    archive = subprocess.run(["git", "archive", "HEAD"], cwd=repo, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if archive.returncode != 0:
        return "git archive failed"
    os.makedirs(destination)
    unpack = subprocess.run(["tar", "-x", "-f", "-", "-C", destination], input=archive.stdout,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if unpack.returncode != 0:
        return "tar failed"
    return None


def main(argv, repo=None):
    parser = argparse.ArgumentParser(prog="forced_failures.py")
    parser.add_argument("--python", action="append", default=[])
    parser.add_argument("--marker", action="append", default=[])
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    pythons = args.python or [sys.executable]
    repo = repo or os.getcwd()
    work = tempfile.mkdtemp(prefix="forced-failures-")
    try:
        root = os.path.join(work, "copy")
        problem = make_copy(repo, root)
        if problem:
            print("forced_failures: could not run: %s" % problem)
            return 2
        tests_dir = os.path.join(root, "tests")
        scope = [("tests/" + name, classes) for name, classes in hygiene.assert_scope(tests_dir)]
        log = None
        log_path = os.path.join(work, "bad-outputs.txt")
        if args.keep:
            log = open(log_path, "w", encoding="utf-8")
        try:
            rows = force(root, scope, pythons, args.marker, work, bad_log=log)
        finally:
            if log is not None:
                log.close()
        if not rows:
            print("forced_failures: could not run: no assertion in scope that this script can flip")
            return 2
        for row in rows:
            print(row_text(row))
        flipped = set(row["rel"] for row in rows)
        empty = [rel for rel, _ in scope if rel not in flipped]
        for rel in empty:
            print("no assertion flipped in: %s" % rel)
        skipped = 0
        for rel, classes in scope:
            skipped += not_flipped(ast.parse(read_bytes_text(os.path.join(root, rel))), classes)
        print("not flipped: %d (assertRaises and fail calls, which this script does not force)"
              % skipped)
        print(totals(rows))
        if args.keep:
            print("kept: %s (output of BAD rows: %s)" % (work, log_path))
        return 1 if empty or [r for r in rows if not r["ok"]] else 0
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
