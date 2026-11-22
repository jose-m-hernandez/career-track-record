"""Tests for the reader contract: the example reader serves `ab` and `panel` folders, starts
its model commands in fresh folders, and gives `codex` a read-only permission profile. All
data here is invented. The case numbers (R1 and so on) are those of the reader-contract spec.

No test starts a real model. The stand-in `codex` is a Python script in a folder of its own
that is the only folder on PATH. The helpers of tests/test_example_reader.py are reached
through the module, never by importing its TestCase class, so that unittest runs no test
twice."""

import ast
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

try:
    import pwd
except ImportError:  # no system list of users, as on Windows
    pwd = None

from tests import test_example_reader as base
from tests import test_packaging
from tests import test_panel as tp

ROOT = base.ROOT
READER = base.READER
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from career_track_record import panel  # noqa: E402

LSOF = "/usr/sbin/lsof"
PROMPT = "invented prompt text"
POSTING = "Data Analyst, Example Corp. Reports in SQL."
A_TEXT = "Alex Example. Analyst, SQL reports."
B_TEXT = "Alex Example. Analyst, SQL and Python reports."
LENS = "You are a recruiter at Example Corp."
FIXTURE_F = {"PROMPT.txt": PROMPT, "POSTING.txt": POSTING, "A.txt": A_TEXT, "B.txt": B_TEXT,
             "LENS.txt": LENS, "DOCUMENT.txt": A_TEXT}
AB_FILES = ("PROMPT.txt", "POSTING.txt", "A.txt", "B.txt")
PANEL_FILES = ("PROMPT.txt", "POSTING.txt", "LENS.txt", "DOCUMENT.txt")
REPLY = ("READ: x\nPRIOR: nothing\nSCORE: 8\nSTRENGTHS: none\nDOUBTS: none\n"
         "UNDERSOLD: none\nOVEREXPLAINED: none\nOWNED: none\nFLAG-FIXES: none\n")
NOTE = ("The four files named in the instructions are pasted below, because you cannot open "
        "files. Treat each block as that file. Reply in the format the instructions give.\n")
AB_STDIN = (NOTE + "\n===== PROMPT.txt (the instructions) =====\n" + PROMPT + "\n"
            "\n===== POSTING.txt (the job posting) =====\n" + POSTING + "\n"
            "\n===== A.txt (version A) =====\n" + A_TEXT + "\n"
            "\n===== B.txt (version B) =====\n" + B_TEXT + "\n")
PANEL_STDIN = (NOTE + "\n===== PROMPT.txt (the instructions) =====\n" + PROMPT + "\n"
               "\n===== LENS.txt (the role to read in) =====\n" + LENS + "\n"
               "\n===== POSTING.txt (the job posting) =====\n" + POSTING + "\n"
               "\n===== DOCUMENT.txt (the document to read) =====\n" + A_TEXT + "\n")
REFUSAL = ("model_reader: cannot tell which kind of read folder this is: an ab folder holds "
           "A.txt and B.txt, a panel folder holds DOCUMENT.txt and LENS.txt, and this one "
           "holds %s\n")
WIDE = ("model_reader: cannot run: codex is installed under %s, which is too wide to grant; "
        "install codex in a folder of its own and run again\n")
CLAUDE_FLAGS = ["-p", "--restricted", "--strict-mcp-config", "--tools", "", "--setting-sources",
                "", "--no-session-persistence"]

# A stand-in `codex`: records what it was given (arguments, standard input, environment, working
# folder, that folder's files, its parent's working folder) and writes REPLY where it is told.
CODEX_STANDIN = '''#!@PYTHON@
import json, os, subprocess, sys
args = sys.argv[1:]
stdin = sys.stdin.read()
cwd = os.getcwd()
files = {}
for name in sorted(os.listdir(cwd)):
    with open(os.path.join(cwd, name), "rb") as handle:
        files[name] = handle.read().hex()
parent_cwd = None
if os.path.exists("/usr/sbin/lsof"):
    out = subprocess.run(["/usr/sbin/lsof", "-a", "-p", str(os.getppid()), "-d", "cwd", "-Fn"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode()
    for line in out.splitlines():
        if line.startswith("n"):
            parent_cwd = line[1:]
parent_listing = None
if parent_cwd and os.path.isdir(parent_cwd):
    parent_listing = sorted(os.listdir(parent_cwd))
call = {"args": args, "stdin": stdin, "env": dict(os.environ), "cwd": cwd,
        "listing": sorted(files), "files": files, "parent_cwd": parent_cwd,
        "parent_listing": parent_listing}
with open(os.path.join(@LOG@, "codex.calls.jsonl"), "a") as handle:
    handle.write(json.dumps(call) + "\\n")
if "--output-last-message" in args:
    with open(args[args.index("--output-last-message") + 1], "w") as handle:
        handle.write(@REPLY@)
sys.stdout.write("progress noise, not the reply\\n")
'''


def standin_source(log):
    return (CODEX_STANDIN.replace("@PYTHON@", sys.executable).replace("@LOG@", repr(log))
            .replace("@REPLY@", repr(REPLY)))


def write_executable(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o755)


def write_files(folder, names, fixture=FIXTURE_F):
    os.makedirs(folder, exist_ok=True)
    for name in names:
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(fixture[name] + "\n")


def listing(folder):
    return sorted((n, os.stat(os.path.join(folder, n)).st_mtime_ns) for n in os.listdir(folder))


def expected_args(install, reply):
    """The argument list of spec section 5.7, written out here and not taken from the reader."""
    profile = ('permissions.reader.filesystem={":minimal"="read", ":workspace_roots"={"."="read"}, '
               '":slash_tmp"="none", ":tmpdir"="none", "%s"="read"}' % install)
    return ["exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--disable",
            "apps", "--color", "never", "-c", 'approval_policy="never"', "-c",
            'default_permissions="reader"', "-c", profile, "-c",
            "shell_environment_policy.inherit=none", "--output-last-message", reply, "-"]


def system_home():
    return pwd.getpwuid(os.getuid()).pw_dir


def load_reader():
    spec = importlib.util.spec_from_file_location("model_reader_contract_test", READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(os.name == "nt", "the stand-ins are POSIX scripts")
class ReaderCase(unittest.TestCase):
    """A scratch root with a stand-in folder, a log folder and a read folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)
        self.bin = os.path.join(self.root, "bin")
        self.log = os.path.join(self.root, "log")
        self.folder = os.path.join(self.root, "read")
        os.makedirs(self.log)
        os.makedirs(self.folder)

    def codex(self, where=None):
        write_executable(os.path.join(where or self.bin, "codex"), standin_source(self.log))

    def claude(self):
        text = base.FAKE % {"python": sys.executable, "fake_dir": self.log, "name": "claude",
                            "reply": base.REPLY}
        write_executable(os.path.join(self.bin, "claude"), text)

    def calls(self, name="codex"):
        path = os.path.join(self.log, name + ".calls.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def reader(self, *args, folder=None, path=None, **env):
        environ = {"PATH": self.bin if path is None else path}
        environ.update(env)
        proc = subprocess.run([sys.executable, "-I", READER] + list(args),
                              cwd=folder or self.folder, env=environ,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


class KindCase(ReaderCase):
    """Step 1: the kind of folder, the paste, the refusal and the errors (R1 and R2, R4 to R10)."""

    def setUp(self):
        ReaderCase.setUp(self)
        self.codex()

    def refused(self, line_start=None, exact=None, **env):
        before = listing(self.folder)
        code, out, err = self.reader(**env)
        self.assertEqual((code, out), (2, ""), err)
        self.assertEqual(err.count("\n"), 1, err)
        if exact is not None:
            self.assertEqual(err, exact)
        else:
            self.assertTrue(err.startswith(line_start), err)
        self.assertEqual(self.calls(), [], "the stand-in was started")
        self.assertEqual(listing(self.folder), before)  # R9

    def test_r1_an_ab_folder_is_pasted_byte_for_byte_as_before(self):
        write_files(self.folder, AB_FILES)
        before = listing(self.folder)
        code, out, err = self.reader()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, REPLY)
        self.assertEqual(self.calls()[0]["stdin"], AB_STDIN)
        self.assertEqual(listing(self.folder), before)

    def test_r2_a_panel_folder_is_pasted_lens_then_posting_then_document(self):
        write_files(self.folder, PANEL_FILES)
        before = listing(self.folder)
        code, out, err = self.reader()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, REPLY)
        self.assertEqual(self.calls()[0]["stdin"], PANEL_STDIN)
        self.assertEqual(listing(self.folder), before)

    def test_r4_an_empty_folder_cannot_read_the_prompt(self):
        self.refused(line_start="model_reader: cannot read PROMPT.txt in the read folder: ")

    def test_r5_a_folder_of_neither_kind_is_refused_holding_none(self):
        write_files(self.folder, ("PROMPT.txt", "POSTING.txt"))
        self.refused(exact=REFUSAL % "none of them")

    def test_r6_a_folder_of_both_kinds_is_refused_naming_what_it_holds(self):
        write_files(self.folder, ("PROMPT.txt", "POSTING.txt", "A.txt", "LENS.txt"))
        self.refused(exact=REFUSAL % "A.txt, LENS.txt")

    def test_r7_all_six_files_are_refused(self):
        write_files(self.folder, sorted(FIXTURE_F))
        self.refused(exact=REFUSAL % "A.txt, B.txt, DOCUMENT.txt, LENS.txt")

    def missing(self, names, gone):
        write_files(self.folder, names)
        os.remove(os.path.join(self.folder, gone))
        self.refused(line_start="model_reader: cannot read %s in the read folder: " % gone)

    def test_r8_an_ab_folder_without_b_is_refused(self):
        self.missing(AB_FILES, "B.txt")

    def test_r8_a_panel_folder_without_lens_is_refused(self):
        self.missing(PANEL_FILES, "LENS.txt")

    def test_r8_a_panel_folder_without_document_is_refused(self):
        self.missing(PANEL_FILES, "DOCUMENT.txt")

    def test_r8_a_panel_folder_without_posting_is_refused(self):
        self.missing(PANEL_FILES, "POSTING.txt")

    def test_r9_a_refused_folder_keeps_its_listing_and_times(self):
        write_files(self.folder, sorted(FIXTURE_F))
        before = listing(self.folder)
        self.reader()
        self.assertEqual(listing(self.folder), before)

    def test_r10_the_model_command_is_chosen_before_the_folder_is_read(self):
        code, out, err = self.reader("gemini")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "model_reader: unknown CLI 'gemini': use codex or claude\n")

    def test_the_kind_chooser_by_name(self):
        module = load_reader()
        for names, kind in ((("A.txt",), "ab"), (("B.txt",), "ab"), (("LENS.txt",), "panel"),
                            (("DOCUMENT.txt",), "panel"), ((), "neither"),
                            (("A.txt", "LENS.txt"), "neither")):
            with tempfile.TemporaryDirectory() as folder:
                for name in names:
                    with open(os.path.join(folder, name), "w"):
                        pass
                self.assertEqual(module.kind_of_folder(folder), kind, names)


class WhereCase(ReaderCase):
    """Step 2: where the model commands start and the codex profile (R3, R15, R17, R21)."""

    def folders(self):
        """An ab folder and a panel folder, each at <root>/<name>/run/reads/armX/1."""
        found = {}
        for kind, names in (("ab", AB_FILES), ("panel", PANEL_FILES)):
            folder = os.path.join(self.root, kind, "run", "reads", "armX", "1")
            write_files(folder, names)
            found[kind] = folder
        return found

    def test_r3_the_codex_arguments_are_the_list_of_the_spec_for_both_kinds(self):
        self.codex()
        install = os.path.realpath(self.bin)
        for kind, folder in self.folders().items():
            code, _out, err = self.reader(folder=folder)
            self.assertEqual((code, err), (0, ""), kind)
            call = self.calls()[-1]
            args = call["args"]
            reply = args[args.index("--output-last-message") + 1]
            self.assertEqual(args, expected_args(install, reply), kind)
            self.assertEqual(os.path.dirname(reply), call["env"]["TMPDIR"], kind)
            self.assertNotEqual(os.path.realpath(os.path.dirname(reply)),
                                os.path.realpath(call["cwd"]), "the reply is in the start folder")

    def test_r3_the_claude_flags_are_the_same_for_both_kinds(self):
        self.claude()
        for kind, folder in self.folders().items():
            code, _out, err = self.reader("claude", folder=folder)
            self.assertEqual((code, err), (0, ""), kind)
            with open(os.path.join(self.log, "claude.calls.jsonl"), encoding="utf-8") as handle:
                last = [json.loads(line) for line in handle][-1]
            self.assertEqual(last["args"], CLAUDE_FLAGS, kind)

    def test_r3_the_environment_is_built_from_nothing(self):
        self.codex()
        name, value = "PLANTED_" + os.urandom(6).hex().upper(), os.urandom(12).hex()
        folder = self.folders()["ab"]
        home = os.path.join(self.root, "somebody")
        for extra, expected_home in (({}, system_home()), ({"HOME": home}, home)):
            code, _out, err = self.reader(folder=folder, **dict(extra, **{name: value}))
            self.assertEqual((code, err), (0, ""))
            env = self.calls()[-1]["env"]
            self.assertEqual(env["PATH"], os.path.realpath(self.bin) + ":/usr/bin:/bin")
            self.assertEqual(env["HOME"], expected_home)
            self.assertTrue(os.path.isabs(env["TMPDIR"]))
            self.assertNotIn(name, env)
            self.assertNotIn(value, env.values())

    @unittest.skipIf(pwd is None, "no system list of users")
    def test_r3_an_empty_home_gives_codex_the_system_listed_home(self):
        self.codex()
        code, _out, err = self.reader(folder=self.folders()["ab"], HOME="")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.calls()[-1]["env"]["HOME"], pwd.getpwuid(os.getuid()).pw_dir)

    def test_r15_the_description_states_both_kinds_and_the_profile(self):
        doc = load_reader().__doc__
        for text in ("track-record panel", "track-record ab", "DOCUMENT.txt", "LENS.txt",
                     "permissions.reader.filesystem", "shell_environment_policy.inherit",
                     "PATH", "HOME", "TMPDIR",
                     "reader-1 | python3 /full/path/to/model_reader.py claude | cost 1 | "
                     "family claude\n",
                     "reader-1 | python3 /full/path/to/model_reader.py claude | cost 1\n"):
            self.assertIn(text, doc)
        self.assertNotIn("--sandbox read-only", doc)

    def components(self, path):
        return [part for part in os.path.realpath(path).split(os.sep) if part]

    def assert_fresh(self, path, read_folder, words=("armX", "1")):
        real, read = os.path.realpath(path), os.path.realpath(read_folder)
        self.assertNotEqual(real, read)
        self.assertNotEqual(os.path.commonpath([real, read]), read, "inside the read folder")
        self.assertNotEqual(os.path.commonpath([real, read]), real, "holds the read folder")
        for part in self.components(path):
            for word in words:
                self.assertFalse(part == word or (len(word) > 1 and word in part),
                                 "%s carries %s" % (path, word))

    def test_r17_codex_starts_in_a_fresh_folder_of_four_copies(self):
        self.codex()
        for kind, folder in self.folders().items():
            before = listing(folder)
            names = AB_FILES if kind == "ab" else PANEL_FILES
            code, out, err = self.reader(folder=folder)
            self.assertEqual((code, out, err), (0, REPLY, ""), kind)
            call = self.calls()[-1]
            self.assertEqual(sorted(call["files"]), sorted(names), kind)
            for name in names:
                with open(os.path.join(folder, name), "rb") as handle:
                    self.assertEqual(call["files"][name], handle.read().hex(), name)
            self.assert_fresh(call["cwd"], folder)
            self.assertEqual(call["stdin"], AB_STDIN if kind == "ab" else PANEL_STDIN)
            self.assertFalse(os.path.exists(call["cwd"]), "the folder was left behind")
            self.assertEqual(listing(folder), before)

    # Known limit: when the tool stops a read at read-timeout it kills the reader without cleanup, so the folders the reader made (one holds the four copies for codex) stay in the temporary folder.
    @unittest.skipUnless(os.path.exists(LSOF), "lsof is not installed")
    def test_r17_the_readers_own_working_folder_is_fresh_and_empty(self):
        self.codex()
        folder = self.folders()["ab"]
        code, _out, err = self.reader(folder=folder)
        self.assertEqual((code, err), (0, ""))
        call = self.calls()[-1]
        parent = call["parent_cwd"]
        self.assertIsNotNone(parent, "lsof did not show the reader's working folder")
        self.assert_fresh(parent, folder)
        self.assertEqual(call["parent_listing"], [], "the reader's folder held a file")
        self.assertFalse(os.path.exists(parent), "the reader's folder was left behind")
        self.assertFalse(os.path.exists(call["env"]["TMPDIR"]),
                         "the folder of the reply file was left behind")

    def test_a_relative_path_entry_resolves_from_the_read_folder_as_before(self):
        # PATH=bin and the read folder as working folder: the program is found in <read>/bin.
        folder = self.folders()["ab"]
        shelf = os.path.join(folder, "bin")
        self.codex(shelf)
        claude = base.FAKE % {"python": sys.executable, "fake_dir": self.log, "name": "claude",
                              "reply": base.REPLY}
        write_executable(os.path.join(shelf, "claude"), claude)
        for argument in ("codex", "claude"):
            code, out, err = self.reader(argument, folder=folder, path="bin")
            self.assertEqual((code, err), (0, ""), argument)
            self.assertTrue(out.strip(), argument)
        self.assertEqual(len(self.calls("codex")), 1)
        self.assertEqual(len(self.calls("claude")), 2)  # the preflight and the call

    def test_r17_claude_starts_in_two_fresh_empty_folders(self):
        self.claude()
        folder = self.folders()["ab"]
        before = listing(folder)
        code, out, err = self.reader("claude", folder=folder)
        self.assertEqual((code, out, err), (0, base.REPLY, ""))
        with open(os.path.join(self.log, "claude.calls.jsonl"), encoding="utf-8") as handle:
            pre, real = [json.loads(line) for line in handle]
        for call in (pre, real):
            self.assertEqual(call["listing"], [])
            self.assert_fresh(call["cwd"], folder)
            self.assertFalse(os.path.exists(call["cwd"]))
        self.assertNotEqual(pre["cwd"], real["cwd"])
        self.assertEqual(listing(folder), before)

    def test_r17_no_folder_name_carries_the_read_folders_name(self):
        self.codex()
        self.claude()
        folder = os.path.join(self.root, "run", "reads", "armQuiet", "lens-sentinel-7f3a")
        write_files(folder, AB_FILES)
        words = ("armQuiet", "lens-sentinel-7f3a", "sentinel", "reads")
        self.assertEqual(self.reader(folder=folder)[0], 0)
        call = self.calls()[-1]
        self.assert_fresh(call["cwd"], folder, words)
        self.assert_fresh(os.path.dirname(call["args"][call["args"].index(
            "--output-last-message") + 1]), folder, words)
        self.assertEqual(self.reader("claude", folder=folder)[0], 0)
        with open(os.path.join(self.log, "claude.calls.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                self.assert_fresh(json.loads(line)["cwd"], folder, words)
        if not call["parent_cwd"]:
            self.skipTest("lsof gave no working folder")
        self.assert_fresh(call["parent_cwd"], folder, words)

    def shim(self, argument):
        """Run the reader with tempfile.tempdir set to a folder that does not exist."""
        shim = os.path.join(self.root, "shim.py")
        with open(shim, "w", encoding="utf-8") as handle:
            handle.write(
                "import importlib.util, os, sys, tempfile\n"
                "tempfile.tempdir = os.path.join(%r, 'does-not-exist')\n"
                "spec = importlib.util.spec_from_file_location('mr', %r)\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "try:\n"
                "    sys.exit(mod.main([%r], os.environ, os.getcwd()))\n"
                "except mod.ReaderError as exc:\n"
                "    sys.stderr.write('model_reader: %%s\\n' %% exc)\n"
                "    sys.exit(exc.code)\n" % (self.root, READER, argument))
        proc = subprocess.run([sys.executable, "-I", shim], cwd=self.folder,
                              env={"PATH": self.bin}, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout.decode(), proc.stderr.decode()

    def test_r21_a_folder_that_cannot_be_made_starts_no_model_command(self):
        self.codex()
        self.claude()
        write_files(self.folder, AB_FILES)
        for argument in ("codex", "claude"):
            code, out, err = self.shim(argument)
            self.assertEqual((code, out), (2, ""), err)
            self.assertEqual(err.count("\n"), 1, err)
            self.assertTrue(err.startswith("model_reader: cannot run: could not make the "
                                           "reader's folder: No such file or directory"), err)
            self.assertEqual(self.calls(), [])
            self.assertFalse(os.path.exists(os.path.join(self.log, "claude.calls.jsonl")))

    def failing_shim(self, argument, fail_at=None, readonly_at=None, chdir=False):
        """Run the reader's `main` with the system's temporary-folder function failing on its
        `fail_at`th call (counting calls), a folder made read-only on its `readonly_at`th call,
        or the first change of working folder refused. Every folder is made under a folder of
        this test's own. Returns (status, stdout, stderr, what that folder holds afterwards)."""
        tmp = os.path.join(self.root, "shimtmp")
        os.makedirs(tmp, exist_ok=True)
        shim = os.path.join(self.root, "failing_shim.py")
        with open(shim, "w", encoding="utf-8") as handle:
            handle.write(
                "import errno, importlib.util, os, sys, tempfile\n"
                "FAIL_AT, READONLY_AT, CHDIR = %r, %r, %r\n"
                "real, real_chdir, state = tempfile.mkdtemp, os.chdir, {'n': 0, 'cd': 0}\n"
                "def mk(*a, **k):\n"
                "    state['n'] += 1\n"
                "    if state['n'] == FAIL_AT:\n"
                "        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))\n"
                "    path = real(*a, **k)\n"
                "    if state['n'] == READONLY_AT:\n"
                "        os.chmod(path, 0o500)\n"
                "    return path\n"
                "def cd(path):\n"
                "    state['cd'] += 1\n"
                "    if CHDIR and state['cd'] == 1:\n"
                "        raise OSError(errno.EACCES, os.strerror(errno.EACCES))\n"
                "    return real_chdir(path)\n"
                "tempfile.mkdtemp, os.chdir, tempfile.tempdir = mk, cd, %r\n"
                "spec = importlib.util.spec_from_file_location('mr', %r)\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "try:\n"
                "    sys.exit(mod.main([%r], os.environ, os.getcwd()))\n"
                "except mod.ReaderError as exc:\n"
                "    sys.stderr.write('model_reader: %%s\\n' %% exc)\n"
                "    sys.exit(exc.code)\n" % (fail_at, readonly_at, chdir, tmp, READER, argument))
        proc = subprocess.run([sys.executable, "-I", shim], cwd=self.folder,
                              env={"PATH": self.bin}, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout.decode(), proc.stderr.decode(), os.listdir(tmp)

    def assert_one_line_exit_2(self, result, words, where):
        code, out, err, left = result
        self.assertEqual((code, out), (2, ""), "%s: %s" % (where, err))
        self.assertEqual(err, "model_reader: cannot run: could not make the reader's folder: "
                              "%s\n" % words, where)
        self.assertEqual(left, [], "%s: a folder was left behind" % where)

    def test_r21_every_folder_the_codex_reader_makes_fails_with_the_one_line(self):
        self.codex()
        write_files(self.folder, AB_FILES)
        for where, kw in (("the reader's own folder", {"fail_at": 1}),
                          ("the codex start folder", {"fail_at": 2}),
                          ("the folder of the reply file", {"fail_at": 3})):
            result = self.failing_shim("codex", **kw)
            self.assert_one_line_exit_2(result, "No space left on device", where)
            self.assertEqual(self.calls(), [], where)

    def test_r21_a_copy_that_cannot_be_written_into_the_codex_start_folder(self):
        self.codex()
        write_files(self.folder, AB_FILES)
        result = self.failing_shim("codex", readonly_at=2)
        self.assert_one_line_exit_2(result, "Permission denied", "the copy")
        self.assertEqual(self.calls(), [])

    def test_r21_a_change_of_working_folder_that_is_refused(self):
        self.codex()
        self.claude()
        write_files(self.folder, AB_FILES)
        for argument in ("codex", "claude"):
            result = self.failing_shim(argument, chdir=True)
            self.assert_one_line_exit_2(result, "Permission denied", argument)
            self.assertEqual(self.calls(), [])
            self.assertEqual(self.calls("claude"), [])

    def test_r21_the_claude_preflight_folder_fails_with_the_one_line(self):
        self.codex()
        self.claude()
        write_files(self.folder, AB_FILES)
        result = self.failing_shim("claude", fail_at=2)
        self.assert_one_line_exit_2(result, "No space left on device", "the preflight folder")
        self.assertEqual(self.calls("claude"), [])

    def test_r21_the_claude_call_folder_fails_before_the_preflight_with_the_one_line(self):
        self.codex()
        self.claude()
        write_files(self.folder, AB_FILES)
        result = self.failing_shim("claude", fail_at=3)
        self.assert_one_line_exit_2(result, "No space left on device", "the call folder")
        self.assertEqual(self.calls("claude"), [], "a model command started")

    def test_r21_control_mkdtemp_raises_file_not_found(self):
        with mock.patch.object(tempfile, "tempdir", os.path.join(self.root, "nope")):
            with self.assertRaises(FileNotFoundError):
                tempfile.mkdtemp()


class GuardCase(ReaderCase):
    """Step 3: the install-folder guard (R20)."""

    def layout(self, standin_at, read_at=None, path=None, home="h", tmpdir="t", link=None):
        """Run the reader on an ab folder, with a stand-in `codex` at <root>/<standin_at>."""
        read = os.path.join(self.root, read_at or "read")
        write_files(read, AB_FILES)
        os.makedirs(os.path.join(self.root, "t"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "h"), exist_ok=True)
        self.codex(os.path.join(self.root, standin_at))
        env = {}
        if home:
            env["HOME"] = os.path.join(self.root, home)
        if tmpdir:
            env["TMPDIR"] = os.path.join(self.root, tmpdir)
        folder_path = path if path is not None else os.path.join(self.root, standin_at)
        return self.reader(folder=read, path=folder_path, **env)

    def assert_refused(self, result, install):
        code, out, err = result
        self.assertEqual((code, out), (2, ""), err)
        self.assertEqual(err, WIDE % os.path.realpath(install))
        self.assertEqual(self.calls(), [], "the stand-in was started")
        self.assertEqual([n for n in os.listdir(os.path.join(self.root, "t")) if n != "codex"],
                         [], "a folder was left behind")

    def assert_allowed(self, result, install):
        code, _out, err = result
        self.assertEqual((code, err), (0, ""))
        args = self.calls()[-1]["args"]
        reply = args[args.index("--output-last-message") + 1]
        self.assertEqual(args, expected_args(os.path.realpath(install), reply))

    def test_r20_a_the_home_folder_is_refused(self):
        self.assert_refused(self.layout("h"), os.path.join(self.root, "h"))

    def test_r20_b_a_folder_holding_the_home_folder_is_refused(self):
        self.assert_refused(self.layout("."), self.root)

    def test_r20_c_a_folder_holding_the_start_folder_is_refused(self):
        self.assert_refused(self.layout("t"), os.path.join(self.root, "t"))

    def test_r20_d_a_folder_holding_the_read_folder_is_refused(self):
        self.assert_refused(self.layout("r", read_at="r/run/reads/armX/1"),
                            os.path.join(self.root, "r"))

    def test_r20_e_a_folder_of_its_own_below_home_is_allowed(self):
        self.assert_allowed(self.layout("h/codex-own"), os.path.join(self.root, "h/codex-own"))

    def test_r20_f_the_layout_of_the_existing_tests_is_allowed(self):
        write_files(self.folder, AB_FILES)
        self.codex()
        self.assert_allowed(self.reader(), self.bin)

    def test_r20_g_a_link_layout_grants_the_folder_of_the_link(self):
        real = os.path.join(self.root, "p", "Caskroom", "codex", "0.156.1", "bin")
        self.codex(real)
        link_folder = os.path.join(self.root, "p", "bin")
        os.makedirs(link_folder)
        os.symlink(os.path.join(real, "codex"), os.path.join(link_folder, "codex"))
        write_files(self.folder, AB_FILES)
        os.makedirs(os.path.join(self.root, "t"))
        result = self.reader(path=link_folder, TMPDIR=os.path.join(self.root, "t"),
                             HOME=os.path.join(self.root, "h"))
        self.assert_allowed(result, link_folder)
        text = " ".join(self.calls()[-1]["args"])
        self.assertNotIn("Caskroom", text)

    def test_r20_the_check_function_by_folder(self):
        module = load_reader()
        other = os.path.join(self.root, "other")
        read, start = os.path.join(other, "read"), os.path.join(other, "start")
        home = os.path.join(self.root, "h")
        listed_home = system_home()
        with mock.patch.dict(os.environ, {"HOME": home}):
            refused = ["/", "/usr", "/usr/local", "/opt", "/opt/homebrew", self.root, home]
            if listed_home.startswith("/Users/"):
                refused.append("/Users")
            refused.append(listed_home)
            for folder in refused:
                with self.assertRaises(module.ReaderError, msg=folder) as caught:
                    module.check_install_folder(folder, read, start)
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual("model_reader: %s\n" % caught.exception,
                                 WIDE % os.path.realpath(folder), folder)
            for folder in ("/opt/homebrew/bin", "/usr/bin", "/opt/bin",
                           os.path.join(home, "codex-own")):
                module.check_install_folder(folder, read, start)
            with self.assertRaises(module.ReaderError):
                module.check_install_folder(other, read, start)
            with self.assertRaises(module.ReaderError):
                module.check_install_folder(read, read, start)
            with self.assertRaises(module.ReaderError):
                module.check_install_folder(start, read, start)


class EndToEndCase(unittest.TestCase):
    """Step 4: a panel run through the tool with the example reader (R13, R16)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = os.path.realpath(self._tmp.name)
        self.bin, self.log = os.path.join(root, "bin"), os.path.join(root, "log")
        os.makedirs(self.log)
        write_executable(os.path.join(self.bin, "codex"), standin_source(self.log))
        self.command = "%s %s" % (shlex.quote(sys.executable), shlex.quote(READER))
        self.setup = tp.Setup(self, lenses=[tp.LENSES[0]], anchor_reads_per_reader="2",
                              reads_per_reader="1",
                              readers=["reader-1 | %s | cost 1" % self.command])

    def track(self, *args):
        env = {"PATH": self.bin, "PYTHONPATH": SRC, "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run([sys.executable, "-m", "career_track_record", "panel"] + list(args),
                              cwd=self.setup.folder, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return proc.returncode, proc.stdout.decode(), proc.stderr.decode()

    def test_r13_a_panel_run_with_the_example_reader_reads_every_folder(self):
        code, out, err = self.track("freeze", "plan.txt")
        self.assertEqual(code, 0, out + err)
        code, out, err = self.track("run", "plan.txt", "--live")
        self.assertEqual(code, 0, out + err)
        lines = out.splitlines()
        for line in ("reads l1 strong: valid=2 of 2 planned",
                     "reads l1 weak: valid=2 of 2 planned",
                     "reads all readers l1 version: valid=1 of 1 planned",
                     "failed reads: 0", "exit status: 0"):
            self.assertIn(line, lines, out)
        self.assertFalse([line for line in lines if line.startswith("DEAD")], out)

    def test_r16_a_run_without_live_prints_exactly_five_lines(self):
        self.assertEqual(self.track("freeze", "plan.txt")[0], 0)
        code, out, err = self.track("run", "plan.txt")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), [
            "live readers are configured: nothing was started and no reply was written; "
            "add --live to run them",
            "reader reader-1: %s (cost 1 per read)" % self.command,
            "planned reads: 5",
            "estimated spend: 5 (the sum of the planned reads' declared costs; the tool cannot "
            "see real spend)",
            "spend ceiling: none"])
        self.assertEqual(os.listdir(self.log), [])


GUIDE = os.path.join(ROOT, "docs", "guides", "panel.md")
AB_GUIDE = os.path.join(ROOT, "docs", "guides", "ab.md")
HEADING = "## Write a reader of your own"
OLD_SENTENCE = ("Readers are the same as in `track-record ab`: a command you name, or the "
                "built-in `fake`.")
NEW_SENTENCE = ("A reader is a command you name, or the built-in `fake`, as in "
                "`track-record ab`; but a `panel` read folder holds different files from an "
                "`ab` one, and [Write a reader of your own](#write-a-reader-of-your-own) says "
                "which.")
AB_SENTENCE = ("A `panel` read folder holds different files; see [the panel guide]"
               "(panel.md#write-a-reader-of-your-own).")


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def headings(text):
    found, fenced = [], False
    for number, line in enumerate(text.split("\n")):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,6} ", line):
            found.append((number, line))
    return found


def section_of(text):
    lines = text.split("\n")
    start = [n for n, line in headings(text) if line == HEADING][0]
    return "\n".join(lines[start:])


def skeleton_of(text):
    blocks = re.findall(r"^```python\n(.*?)^```$", section_of(text), re.S | re.M)
    assert len(blocks) == 1, len(blocks)
    return blocks[0]


class DocsCase(unittest.TestCase):
    """Step 5: the panel guide and the one sentence of the ab guide (R11, R12)."""

    def test_r11_the_panel_guide_has_the_new_sentence_and_section(self):
        text = read_text(GUIDE)
        self.assertNotIn(OLD_SENTENCE, text)
        self.assertIn(NEW_SENTENCE, text)
        self.assertEqual(headings(text)[-1][1], HEADING)
        section = section_of(text)
        for word in ("PROMPT.txt", "LENS.txt", "POSTING.txt", "DOCUMENT.txt", "REPLY.txt",
                     "STDERR.txt", "READ", "PRIOR", "SCORE", "CRITERION-<name>", "STRENGTHS",
                     "DOUBTS", "UNDERSOLD", "OVEREXPLAINED", "OWNED", "FLAG-FIXES",
                     "missing SCORE"):
            self.assertIn(word, section)
        self.assertIn(AB_SENTENCE, read_text(AB_GUIDE))

    def run_skeleton(self, criteria):
        script = skeleton_of(read_text(GUIDE))
        with tempfile.TemporaryDirectory() as scratch, tempfile.TemporaryDirectory() as folder:
            path = os.path.join(scratch, "my_panel_reader.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(script)
            write_files(folder, ("POSTING.txt", "LENS.txt", "DOCUMENT.txt"))
            with open(os.path.join(folder, "PROMPT.txt"), "w", encoding="utf-8") as handle:
                handle.write(panel.prompt_of(criteria))
            before = listing(folder)
            proc = subprocess.run([sys.executable, "-I", path], cwd=folder,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env={"PATH": "/usr/bin:/bin"})
            self.assertEqual(listing(folder), before, "the skeleton wrote a file")
        self.assertEqual((proc.returncode, proc.stderr), (0, b""))
        return script, proc.stdout.decode("utf-8")

    def test_r12_the_skeleton_prints_a_reply_the_tool_accepts(self):
        script, out = self.run_skeleton(())
        reply = panel.parse_reply(out)
        self.assertIsNone(reply.failure)
        self.assertIsInstance(reply.score, int)
        modules = [alias.name for node in ast.walk(ast.parse(script))
                   if isinstance(node, (ast.Import, ast.ImportFrom))
                   for alias in (node.names if isinstance(node, ast.Import) else
                                 [ast.alias(name=node.module)])]
        self.assertEqual(modules, ["re"])

    def test_r12_the_skeleton_scores_each_criterion_of_a_lens_that_names_them(self):
        _script, out = self.run_skeleton(("a", "b"))
        lines = out.splitlines()
        self.assertTrue([line for line in lines if line.startswith("CRITERION-a: ")])
        self.assertTrue([line for line in lines if line.startswith("CRITERION-b: ")])
        self.assertFalse([line for line in lines if line.startswith("SCORE")])
        reply = panel.parse_reply(out, ("a", "b"))
        self.assertIsNone(reply.failure)
        self.assertIsInstance(reply.score, int)
        # Each criterion score is accepted by itself, as a whole number, and the tool's score
        # is their sum.
        parts = []
        for name in ("a", "b"):
            value = reply.fields[panel.CRITERION + name]
            self.assertIsNotNone(panel.harness.whole_number(value), "%s is not a whole number" % name)
            parts.append(panel.harness.whole_number(value))
        self.assertEqual(reply.score, sum(parts))


class SignedGuideLines(unittest.TestCase):
    """The two signed lines: the ab guide's passage on the codex command, and the known-issue
    bullet in the changelog. Both are embedded here as signed."""

    LINE1 = ('For Codex it runs `codex exec --skip-git-repo-check --ephemeral --ignore-user-config --disable apps --color never -c approval_policy="never" -c default_permissions="reader" -c permissions.reader.filesystem=<profile> -c shell_environment_policy.inherit=none --output-last-message <temp file> -`, in a fresh folder that holds copies of the four files, not in the read folder: a permission profile, set by this example reader and not by the tool, that lets the commands the model runs read that folder, the system\'s own files and the folder Codex is installed in and grants no write, no approval prompts, no saved session, your Codex `config.toml` skipped, an environment of `PATH`, `HOME` and `TMPDIR` only for the Codex process itself, and only the model\'s final message used as the reply (`--skip-git-repo-check` because that folder is not a git repository). In checks with `codex sandbox` (Codex 0.156.1, no model call), a write in that folder was refused under that profile, so the commands the model runs are not meant to change your files; whether the commands a `codex exec` run issues get the same profile has not been measured in a live run. The reader also passes `--disable apps`, which is meant to turn off Codex\'s apps and connectors feature.')
    LINE2 = ("- **Example reader: a read that times out leaves its folders behind.** When a read reaches `read-timeout`, the tool stops the reader without letting it clean up, so the fresh folders it made under your system temporary folder stay there: three, with random names, and for `codex` one of them holds copies of that read's four files. Delete them yourself.")

    def read(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_the_ab_guide_holds_the_signed_passage_once(self):
        self.assertEqual(self.read("docs", "guides", "ab.md").count(self.LINE1), 1)

    def test_the_ab_guide_has_no_sandbox_read_only(self):
        self.assertNotIn("--sandbox read-only", self.read("docs", "guides", "ab.md"))

    def test_the_released_changelog_section_lists_the_known_issue_once(self):
        text = self.read("CHANGELOG.md")
        start = text.index("## [0.14.1]")
        end = text.index("\n## [", start)
        section = text[start:end]
        self.assertIn("\n### Known issues\n", section)
        after = section[section.index("\n### Known issues\n"):]
        self.assertEqual(after.count(self.LINE2), 1)


if __name__ == "__main__":
    unittest.main()
