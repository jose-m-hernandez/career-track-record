"""Test hygiene rule: a new test builds its child environment from nothing, and a test that starts
a child process asserts with a fixed message, so a failure never prints what a child wrote.

For a checked module or class, a finding is any of:
  R1, always: an attribute access named `environ` (that is how `os.environ` appears in a syntax
      tree), and `from os import environ` (with or without `as`), a finding at the import line.
  R2, always: use of an older test module's helper that copies the environment. A name listed in
      ENV_HELPERS or ENV_CLASSES imported with `from tests.<module> import <name>` (with or
      without `as`) is a finding at the import line; so is `<alias>.<name>` where the alias was
      bound by `from tests import <module>`, `import tests.<module>` or
      `import tests.<module> as <alias>`. A relative import counts as its tests form:
      `from .<module> import <name>` and `from . import <module>`.
  R3, only in a child-process module: a call `self.assertX(...)` other than these forms:
      `self.assertTrue(<expr>, "<literal>")` and `self.assertFalse(<expr>, "<literal>")`:
          exactly two arguments, the second a plain string literal;
      `self.assertEqual(code, <integer literal>, "<literal>")`: the first argument the bare name
          `code`;
      `with self.assertRaises(<exception>):` with one argument;
      a call to a method named in ASSERT_HELPERS (project helpers), which is always allowed;
      or `self.fail(...)` with anything but one plain string literal.
  In a module that is not a child-process module (as defined below), R3 does not apply.

A child-process module is one that imports a module named in CHILD_MODULES, or imports any name
from another test module (`from tests... import ...`, `import tests...`, or the relative forms
`from .<module> import ...` and `from . import ...`), or calls a function named in OS_CHILD on
the os module (`os.system(...)`, `<alias>.popen(...)` after `import os as <alias>`), or imports
one of those functions from os by name. For a class, the question is asked of its whole module.
Other ways to start a process (os.exec*, os.spawn*, os.posix_spawn, multiprocessing, pty) are
not detected.

The scope is data: LEGACY lists the test modules that predate the rule and are not checked;
CLASSES names the classes that are checked inside a legacy module; every other `tests/test_*.py`
is checked whole. Add a module to LEGACY on purpose or not at all.

Used by tests/test_test_hygiene.py and ci/forced_failures.py."""

import ast
import glob
import os

LEGACY = (
    "test_ab.py",
    "test_ab_document.py",
    "test_ab_escape.py",
    "test_ab_live.py",
    "test_ab_reader_command.py",
    "test_ab_rev2.py",
    "test_ab_rev3.py",
    "test_ab_rev4.py",
    "test_ab_rev4_runs.py",
    "test_ab_rev5_series.py",
    "test_ab_rev5_series_recheck.py",
    "test_ab_rev5_tie.py",
    "test_ab_run_failures.py",
    "test_ab_vr1.py",
    "test_ab_vr2.py",
    "test_absence.py",
    "test_absence_pdf.py",
    "test_barred.py",
    "test_barred_pdf_layout.py",
    "test_barred_soft_hyphen.py",
    "test_barred_strings.py",
    "test_claims.py",
    "test_claims_require_sources.py",
    "test_claims_runs.py",
    "test_claims_sources.py",
    "test_cli.py",
    "test_config.py",
    "test_drafts.py",
    "test_drafts_docs.py",
    "test_drafts_inputs.py",
    "test_example_keywords.py",
    "test_example_reader.py",
    "test_freeze_reader_warning.py",
    "test_help_lines.py",
    "test_keywords.py",
    "test_live_profile_check.py",
    "test_no_network.py",
    "test_output_failures.py",
    "test_packaging.py",
    "test_panel.py",
    "test_panel_rev2.py",
    "test_panel_rev3.py",
    "test_panel_rev4.py",
    "test_panel_rev4_runs.py",
    "test_parse.py",
    "test_parse_pdf.py",
    "test_pdf_text.py",
    "test_placeholders.py",
    "test_posting_file.py",
    "test_provenance.py",
    "test_quote_check.py",
    "test_reader_contract.py",
    "test_reader_profile.py",
    "test_readme_diagram.py",
    "test_readme_truth.py",
    "test_record_check.py",
    "test_record_check_inputs.py",
    "test_record_docs.py",
    "test_record_folder.py",
    "test_resolution.py",
    "test_setup.py",
    "test_source_hygiene.py",
    "test_spec_readings.py",
    "test_spec_revisions.py",
    "test_stats.py",
    "test_tone.py",
    "test_tone_pdf.py",
    "test_wrapped_compounds.py",
    "test_wrapped_compounds_pdf.py",
    "test_write_recheck.py",
)

CLASSES = {"test_example_reader.py": ("FakePlanCase", "FirstPlanCase")}

ASSERT_HELPERS = ("assertCannot", "assertCannotRun", "assertRefused", "assertRun")

CHILD_MODULES = ("ci.barred_strings", "ci.forced_failures", "subprocess")

OS_CHILD = ("popen", "system")

ENV_HELPERS = (
    ("test_barred.py", "clean_env"),
    ("test_barred_pdf_layout.py", "clean_env"),
    ("test_barred_soft_hyphen.py", "clean_env"),
    ("test_cli.py", "track"),
    ("test_cli.py", "track_with_broken_stdout"),
    ("test_help_lines.py", "help_of"),
    ("test_output_failures.py", "env"),
    ("test_parse.py", "env"),
    ("test_parse_pdf.py", "env"),
    ("test_pdf_text.py", "run_cli"),
    ("test_record_check.py", "env"),
    ("test_record_folder.py", "git_env"),
    ("test_tone.py", "run_cli"),
    ("test_tone_pdf.py", "run_cli"),
    ("test_wrapped_compounds.py", "env"),
    ("test_wrapped_compounds_pdf.py", "env"),
)

ENV_CLASSES = (
    ("test_barred_strings.py", "Case"),
    ("test_claims.py", "ClaimsCase"),
    ("test_claims_sources.py", "NotRegularFiles"),
    ("test_example_keywords.py", "KeywordsExampleCase"),
    ("test_quote_check.py", "QuoteCase"),
)

_LISTED = frozenset(ENV_HELPERS) | frozenset(ENV_CLASSES)


def _is_string(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_int(node):
    return (isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool))


def _is_tests_module(name):
    return name == "tests" or name.startswith("tests.")


def from_module(sub):
    """The absolute module a `from ... import` names, or None. The modules checked sit in
    tests/, so a relative import of level 1 names the tests package: `from .X import n` is
    `from tests.X import n` and `from . import X` is `from tests import X`. A level of 2 or
    more names no tests module and is None."""
    if not sub.level:
        return sub.module
    if sub.level == 1:
        return "tests." + sub.module if sub.module else "tests"
    return None


def _os_names(tree):
    """The names bound to the os module by `import os` or `import os as <alias>`."""
    names = set()
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Import):
            for alias in sub.names:
                if alias.name == "os":
                    names.add(alias.asname or "os")
    return names


def is_child_process(tree):
    """True when the module tree imports a module in CHILD_MODULES, or any name from another
    test module, or starts a child process with a function of os named in OS_CHILD (called on
    the os module, or imported from it by name)."""
    os_names = _os_names(tree)
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Import):
            for alias in sub.names:
                if alias.name in CHILD_MODULES or _is_tests_module(alias.name):
                    return True
        elif isinstance(sub, ast.ImportFrom) and from_module(sub):
            module = from_module(sub)
            if module in CHILD_MODULES or _is_tests_module(module):
                return True
            for alias in sub.names:
                if "%s.%s" % (module, alias.name) in CHILD_MODULES:
                    return True
                if module == "os" and alias.name in OS_CHILD:
                    return True
        elif (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
              and sub.func.attr in OS_CHILD and isinstance(sub.func.value, ast.Name)
              and sub.func.value.id in os_names):
            return True
    return False


def import_findings(tree):
    """The findings at an import line: R1 for `from os import environ` under any name, and R2 for
    listed names imported with `from tests.<module> import <name>` (or its relative form)."""
    found = []
    for sub in ast.walk(tree):
        if not isinstance(sub, ast.ImportFrom):
            continue
        module = from_module(sub)
        if module == "os":
            for alias in sub.names:
                if alias.name == "environ":
                    found.append((sub.lineno, "imports environ"))
        if module and module.startswith("tests."):
            for alias in sub.names:
                if (module[len("tests."):] + ".py", alias.name) in _LISTED:
                    found.append((sub.lineno, "imports %s, which copies the environment"
                                  % alias.name))
    return sorted(found)


def _aliases(tree):
    """Map a name bound to a test module to that module's file name, and the dotted
    `tests.<module>` chain from `import tests.<module>`."""
    names = {}
    for sub in ast.walk(tree):
        if isinstance(sub, ast.ImportFrom) and from_module(sub) == "tests":
            for alias in sub.names:
                names[alias.asname or alias.name] = alias.name + ".py"
        elif isinstance(sub, ast.Import):
            for alias in sub.names:
                if alias.name.startswith("tests.") and alias.name.count(".") == 1:
                    module = alias.name[len("tests."):] + ".py"
                    names[alias.asname or alias.name] = module
    return names


def findings(node, child_process, tree=None):
    """Return a list of (line number, text) for one module or class syntax tree.

    child_process says whether R3 applies. tree is the whole module tree, needed for R2 when node
    is one class; it defaults to node. The import-line findings are included only when node is
    the module (scan adds them once for a class)."""
    found = []
    if tree is None:
        tree = node
    if node is tree:
        found.extend(import_findings(tree))
    aliases = _aliases(tree)
    managers = set()
    for sub in ast.walk(node):
        if isinstance(sub, (ast.With, ast.AsyncWith)):
            for item in sub.items:
                managers.add(id(item.context_expr))
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "environ":
            found.append((sub.lineno, "uses environ"))
        if isinstance(sub, ast.Attribute):
            base, module = sub.value, None
            if isinstance(base, ast.Name) and base.id in aliases:
                module = aliases[base.id]
            elif (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                  and base.value.id == "tests" and "tests." + base.attr in aliases):
                module = aliases["tests." + base.attr]
            if module is not None and (module, sub.attr) in _LISTED:
                found.append((sub.lineno, "uses %s, which copies the environment" % sub.attr))
        if not child_process:
            continue
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and isinstance(sub.func.value, ast.Name) and sub.func.value.id == "self"):
            continue
        name = sub.func.attr
        if name in ASSERT_HELPERS:
            continue
        if not (name.startswith("assert") or name == "fail"):
            continue
        args = sub.args
        plain = not sub.keywords
        if name in ("assertTrue", "assertFalse"):
            if not (plain and len(args) == 2 and _is_string(args[1])):
                found.append((sub.lineno, "%s without a fixed message" % name))
        elif name == "assertEqual":
            ok = (plain and len(args) == 3 and isinstance(args[0], ast.Name)
                  and args[0].id == "code" and _is_int(args[1]) and _is_string(args[2]))
            if not ok:
                found.append((sub.lineno, "assertEqual not of the form (code, <int>, <literal>)"))
        elif name == "assertRaises":
            if not (plain and len(args) == 1 and id(sub) in managers):
                found.append((sub.lineno, "assertRaises not a context manager with one argument"))
        elif name == "fail":
            if not (plain and len(args) == 1 and _is_string(args[0])):
                found.append((sub.lineno, "fail without one literal message"))
        else:
            found.append((sub.lineno, "%s is not allowed" % name))
    return sorted(found)


def class_nodes(tree, names):
    """The top-level classes of a module tree whose names are in names."""
    return [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]


def scope(tests_dir):
    """Return a list of (file name, class names or None) in scope, sorted by file name.
    None means the whole module is checked."""
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(tests_dir, "test_*.py")))
    out = []
    for name in names:
        if name in CLASSES:
            out.append((name, tuple(CLASSES[name])))
        elif name not in LEGACY:
            out.append((name, None))
    return out


def read_tree(path):
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    return source, ast.parse(source)


def assert_scope(tests_dir):
    """The entries of scope(tests_dir) whose module is a child-process module."""
    out = []
    for name, classes in scope(tests_dir):
        _, tree = read_tree(os.path.join(tests_dir, name))
        if is_child_process(tree):
            out.append((name, classes))
    return out


def scan(tests_dir):
    """Return a list of 'file:line text' for every finding in scope."""
    out = []
    for name, classes in scope(tests_dir):
        _, tree = read_tree(os.path.join(tests_dir, name))
        child = is_child_process(tree)
        if classes is None:
            got = findings(tree, child)
        else:
            got = list(import_findings(tree))
            for node in class_nodes(tree, classes):
                got.extend(findings(node, child, tree))
            got.sort()
        for lineno, text in got:
            out.append("%s:%d %s" % (name, lineno, text))
    return out
