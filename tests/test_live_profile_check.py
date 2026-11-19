"""Tests for tests/live_profile_check.py, the script of case R19. All data here is invented.

These tests run the script with NO account and no model: the only program on PATH is a stand-in
`codex` that replays an event stream. The script's live mode is never run against a real
`codex`."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "tests", "live_profile_check.py")
VERSION = "codex-cli 0.156.1"

# The stand-in: `--version` prints the version it was built with; any other call records itself,
# reads the nine commands out of the message it is given and prints one event for each, shaped
# by MODE, as `codex exec --json` is read to do.
STANDIN = '''#!@PYTHON@
import json, os, re, sys
MODE, VERSION, LOG = @MODE@, @VERSION@, @LOG@
args = sys.argv[1:]
if args == ["--version"]:
    sys.stdout.write(VERSION + "\\n")
    sys.exit(0)
stdin = sys.stdin.read()
with open(os.path.join(LOG, "exec.json"), "a") as handle:
    handle.write(json.dumps({"args": args, "cwd": os.getcwd(), "env": dict(os.environ)}) + "\\n")
commands = re.findall(r"^\\d\\. (.+)$", stdin, re.M)
with open("POSTING.txt") as handle:
    posting = handle.read().strip()


def event(number, command, status, output):
    return {"type": "item.completed", "item": {"id": "item_%d" % number, "type": "command_execution",
            "command": "/bin/zsh -lc '%s'" % command, "aggregated_output": output,
            "exit_code": status, "status": "completed"}}


def path_of(command):
    path = command[len("cat "):]
    return os.path.join(os.getcwd(), path) if path.startswith("../") else path


rows = []
for number, command in enumerate(commands, 1):
    if number == 1:
        row = (0, posting + "\\n")
    elif number <= 6:
        row = (1, "cat: %s: Operation not permitted\\n" % command[len("cat "):])
    elif number == 7:
        names = ["CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "PWD", "SHLVL", "_",
                 "NODE_REPL_HISTORY"]
        row = (0, "".join(n + "\\n" for n in names + (["SECRET_THING"] if MODE == "env" else [])))
        if MODE == "emptyenv":
            row = (1, "")
    elif number == 8:
        row = (0, "  PID TTY TIME CMD\\n  501 ttys000 0:00 sleep\\n" if MODE == "ps"
               else "ps: Operation not permitted\\n")
    else:
        row = (0, "2\\n" if MODE == "lsof" else "1\\n")
        if MODE == "emptylsof":
            row = (1, "")
    if MODE == "emptyps" and number == 8:
        row = (1, "")
    kind, _, which = MODE.partition(":")
    if kind == "succeed" and number == int(which):
        row = (0, "something\\n")
    if MODE == "posting" and number == 1:
        row = (1, "cat: POSTING.txt: No such file or directory\\n")
    rows.append(event(number, command, *row))
out = [{"type": "thread.started", "thread_id": "t1"}, {"type": "turn.started"}]
kind, _, which = MODE.partition(":")
for number, row in enumerate(rows, 1):
    if kind == "skip" and number == int(which):
        continue
    out.append(row)
if kind == "leak":
    with open(path_of(commands[int(which) - 1])) as handle:
        out.append({"type": "item.completed", "item": {"id": "x", "type": "agent_message",
                                                       "text": handle.read().strip()}})
out.append({"type": "turn.completed"})
for line in out:
    sys.stdout.write(json.dumps(line) + "\\n")
sys.exit(3 if MODE == "exit3" else 0)
'''


def measured_on_macos(test):
    """Skip a test that runs the baseline (the real ps, lsof and env): the spec's measurements
    are those of macOS."""
    return unittest.skipUnless(sys.platform == "darwin" and os.path.exists("/usr/sbin/lsof"),
                               "R19 is measured on macOS")(test)


def load_script():
    spec = importlib.util.spec_from_file_location("live_profile_check_under_test", LIVE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gone_process(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


@unittest.skipIf(os.name == "nt", "the stand-in is a POSIX script")
class LiveCheckCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = os.path.realpath(self._tmp.name)
        self.bin = os.path.join(self.base, "bin")
        self.log = os.path.join(self.base, "log")
        self.home = os.path.join(self.base, "home")
        for folder in (self.bin, self.log, self.home):
            os.makedirs(folder)
        self.module = load_script()
        self.roots = []
        self.addCleanup(self.drop_roots)

    def drop_roots(self):
        import shutil
        for root in self.roots:
            shutil.rmtree(root, ignore_errors=True)

    def standin(self, mode="pass", version=VERSION):
        path = os.path.join(self.bin, "codex")
        text = (STANDIN.replace("@PYTHON@", sys.executable).replace("@MODE@", repr(mode))
                .replace("@VERSION@", repr(version)).replace("@LOG@", repr(self.log)))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(path, 0o755)

    def execs(self):
        path = os.path.join(self.log, "exec.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def run_script(self, argv=("--live",), plant=None):
        """Run the script in this process, with the stand-in the only program on PATH."""
        out = io.StringIO()
        patches = [mock.patch.dict(os.environ, {"PATH": self.bin, "HOME": self.home}),
                   contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO())]
        if plant is not None:
            patches.append(mock.patch.object(self.module, "plant", plant))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            code = self.module.main(list(argv))
        self.roots += self.lines(out.getvalue(), "R19 root: ")
        return code, out.getvalue()

    def lines(self, out, prefix):
        return [line[len(prefix):] for line in out.splitlines() if line.startswith(prefix)]

    def assert_cleaned(self, out):
        for path in self.lines(out, "R19 planted: "):
            self.assertFalse(os.path.exists(path), "left behind: " + path)
        for pid in self.lines(out, "R19 sleep pid: "):
            self.assertTrue(gone_process(int(pid)), "the sleep is still running")
        for root in self.lines(out, "R19 root: "):
            self.roots.append(root)
            if os.path.exists(root):
                self.assertLessEqual(set(os.listdir(root)), {"stream.jsonl", "facts.json"})
        for shown in self.lines(out, "R19 ls: "):
            self.assertIn("No such file or directory", shown)

    def result(self, out):
        return self.lines(out, "R19 RESULT: ")

    def test_the_script_is_not_a_test_module(self):
        self.assertFalse(os.path.basename(LIVE).startswith("test"))

    @measured_on_macos
    def test_a_clean_stream_passes_and_the_result_line_carries_the_version(self):
        self.standin("pass")
        code, out = self.run_script()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.result(out), ["PASS: %s: exit 0" % VERSION])
        self.assertEqual(self.lines(out, "R19 FAIL: "), [])
        self.assertEqual(len(self.execs()), 1)
        self.assert_cleaned(out)

    @measured_on_macos
    def test_the_call_is_one_codex_exec_with_json_before_the_reply_file(self):
        self.standin("pass")
        self.run_script()
        call = self.execs()[0]
        args = call["args"]
        self.assertLess(args.index("--json"), args.index("--output-last-message"))
        self.assertEqual(sorted(call["env"].keys() & {"PATH", "HOME", "TMPDIR"}),
                         ["HOME", "PATH", "TMPDIR"])

    @measured_on_macos
    def test_the_folder_lies_under_the_roots_t_folder_and_the_stream_is_outside_the_read_folder(self):
        self.standin("pass")
        _code, out = self.run_script()
        root = self.lines(out, "R19 root: ")[0]
        call = self.execs()[0]
        self.assertTrue(os.path.realpath(call["cwd"]).startswith(os.path.join(root, "t") + os.sep))
        self.assertEqual(self.lines(out, "R19 stream: "), [os.path.join(root, "stream.jsonl")])
        self.assertTrue(os.path.exists(os.path.join(root, "stream.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(root, "facts.json")))

    def test_no_flag_prints_the_usage_and_exits_2_with_no_call(self):
        self.standin("pass")
        proc = subprocess.run([sys.executable, LIVE], env={"PATH": self.bin},
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage: python3 tests/live_profile_check.py --live", proc.stderr.decode())
        self.assertIn("R19 REFUSED:", proc.stdout.decode())
        self.assertEqual(self.execs(), [])

    @measured_on_macos
    def test_a_script_run_as_a_program_passes(self):
        self.standin("pass")
        proc = subprocess.run([sys.executable, LIVE, "--live"], stdin=subprocess.DEVNULL,
                              env=dict(os.environ, PATH=self.bin, HOME=self.home),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = proc.stdout.decode()
        self.assertEqual(proc.returncode, 0, out + proc.stderr.decode())
        self.assertIn("R19 RESULT: PASS: %s: exit 0" % VERSION, out)
        self.assert_cleaned(out)

    def test_another_version_is_refused_with_no_call(self):
        self.standin("pass", version="codex-cli 0.155.0")
        code, out = self.run_script()
        self.assertEqual(code, 2)
        self.assertIn("R19 REFUSED: codex --version printed 'codex-cli 0.155.0'", out)
        self.assertEqual(self.execs(), [])

    def test_a_missing_codex_is_refused(self):
        code, out = self.run_script()
        self.assertEqual(code, 2)
        self.assertIn("R19 REFUSED: codex is not installed", out)

    def test_each_precondition_miss_is_refused_before_any_call(self):
        # The planted files are written in this order: K, S, H, T, Q, then the folder's four.
        self.standin("pass")
        for index, name in ((0, "K"), (1, "S"), (2, "H"), (3, "T"), (4, "Q"), (6, "I")):
            original = self.module.plant
            counter = []

            def broken(path, text, index=index, counter=counter, original=original):
                counter.append(path)
                original(path, "the wrong token\n" if len(counter) - 1 == index else text)

            code, out = self.run_script(plant=broken)
            self.assertEqual(code, 2, (name, out))
            self.assertIn("R19 REFUSED: the planted file for %s is missing or holds the wrong "
                          "token" % name, out)
            self.assertEqual(self.execs(), [], name)
            self.assert_cleaned(out)

    def fails(self, mode, expect):
        self.standin(mode)
        code, out = self.run_script()
        self.assertEqual(code, 1, (mode, out))
        failed = self.lines(out, "R19 FAIL: ")
        self.assertTrue([line for line in failed if line.startswith(expect)], (mode, failed))
        self.assertEqual(self.result(out), ["FAIL: %s: exit 1" % VERSION])
        self.assertEqual(len(self.execs()), 1)
        self.assert_cleaned(out)
        return out

    @measured_on_macos
    def test_a_sandbox_read_that_succeeds_fails_for_each_of_the_five(self):
        for number, label in ((2, "S"), (3, "H"), (4, "T"), (5, "Q"), (6, "K")):
            self.setUp_again()
            self.fails("succeed:%d" % number, "outside read %s: " % label)

    def setUp_again(self):
        """A fresh stand-in log between the rounds of one test."""
        path = os.path.join(self.log, "exec.json")
        if os.path.exists(path):
            os.remove(path)

    @measured_on_macos
    def test_each_token_in_an_event_fails_with_its_own_line(self):
        for number, label in ((2, "S"), (3, "H"), (4, "T"), (5, "Q"), (6, "K")):
            self.setUp_again()
            self.fails("leak:%d" % number, "token %s: " % label)

    @measured_on_macos
    def test_a_name_outside_the_allowed_set_fails(self):
        self.fails("env", "env: names outside the allowed set: SECRET_THING")

    @measured_on_macos
    def test_a_process_line_from_ps_fails(self):
        self.fails("ps", "ps: ")

    @measured_on_macos
    def test_an_lsof_count_that_differs_from_the_baseline_fails(self):
        self.fails("lsof", "lsof: count '2', baseline 1")

    @measured_on_macos
    def test_a_command_with_no_event_fails(self):
        for number in (1, 5, 9):
            self.setUp_again()
            self.fails("skip:%d" % number, "no event: command %d has no event" % number)

    @measured_on_macos
    def test_a_posting_that_cannot_be_read_fails(self):
        self.fails("posting", "posting read: cat POSTING.txt gave exit status 1")

    @measured_on_macos
    def test_a_planted_file_that_survives_the_cleanup_fails_the_run(self):
        self.standin("pass")
        kept = []
        original = self.module.remove

        def keep_the_tmp_file(path):
            if os.path.dirname(path) == "/tmp" and os.path.basename(path).startswith("r19-"):
                kept.append(path)
                return
            original(path)

        with mock.patch.object(self.module, "remove", keep_the_tmp_file):
            code, out = self.run_script()
        for path in kept:
            os.remove(path)
        self.assertEqual(len(kept), 1)
        self.assertEqual(code, 1, out)
        self.assertIn("R19 FAIL: cleanup: a planted file is still there: %s" % kept[0], out)

    @measured_on_macos
    def test_a_codex_that_exits_nonzero_fails(self):
        self.fails("exit3", "codex exit status: codex ended with 3")

    @measured_on_macos
    def test_judge_passes_a_saved_pass_stream_with_no_model_call(self):
        self.standin("pass")
        _code, out = self.run_script()
        stream = os.path.join(self.lines(out, "R19 root: ")[0], "stream.jsonl")
        self.setUp_again()
        os.remove(os.path.join(self.bin, "codex"))
        code, out = self.run_script(("--judge", stream))
        self.assertEqual(code, 0, out)
        self.assertIn("R19 RESULT: PASS: %s (recorded when the stream was saved): exit 0"
                      % VERSION, out)
        self.assertEqual(self.execs(), [])

    @measured_on_macos
    def test_judge_fails_a_saved_fail_stream_and_a_corrected_script_judges_the_same_bytes(self):
        self.standin("leak:2")
        _code, out = self.run_script()
        stream = os.path.join(self.lines(out, "R19 root: ")[0], "stream.jsonl")
        with open(stream, "rb") as handle:
            before = handle.read()
        code, out = self.run_script(("--judge", stream))
        self.assertEqual(code, 1, out)
        self.assertIn("R19 FAIL: token S: ", out)
        with open(stream, "rb") as handle:
            self.assertEqual(handle.read(), before)

    @measured_on_macos
    def test_judge_fails_an_env_that_is_not_fewer_names_than_the_baseline(self):
        self.standin("pass")
        _code, out = self.run_script()
        root = self.lines(out, "R19 root: ")[0]
        with open(os.path.join(root, "facts.json"), encoding="utf-8") as handle:
            facts = json.load(handle)
        facts["baseline"]["env_names"] = 3
        with open(os.path.join(root, "facts.json"), "w", encoding="utf-8") as handle:
            json.dump(facts, handle)
        code, out = self.run_script(("--judge", os.path.join(root, "stream.jsonl")))
        self.assertEqual(code, 1)
        self.assertIn("R19 FAIL: env: 6 names, not fewer than the baseline's 3", out)

    @measured_on_macos
    def test_an_env_command_that_failed_and_printed_nothing_fails(self):
        self.fails("emptyenv", "env: no name printed (the command gave no output)")

    @measured_on_macos
    def test_a_ps_command_that_printed_nothing_fails(self):
        self.fails("emptyps", "ps: 0 process line(s), and the output does not hold")

    @measured_on_macos
    def test_an_lsof_command_that_printed_nothing_fails(self):
        self.fails("emptylsof", "lsof: count '', baseline 1")

    def judged(self, **replace):
        """The failures judge() gives for a hand-made stream (no baseline run): the nine
        commands, each with its event, where `replace` swaps the (status, output) of one."""
        paths = {"S": "/x/s", "H": "/x/h", "T": "/x/t", "Q": "/x/q", "K": "/x/k"}
        commands = self.module.commands_of(paths)
        tokens = dict((name, name.lower() * 8) for name in "KSHTQI")
        rows = {1: (0, tokens["I"] + "\n"), 7: (0, "CODEX_SANDBOX\nPWD\nSHLVL\n_\n"),
                8: (0, "ps: Operation not permitted\n"), 9: (0, "1\n")}
        for number in range(2, 7):
            rows[number] = (1, "cat: x: Operation not permitted\n")
        for key, value in replace.items():
            rows[int(key[1:])] = value
        lines = [json.dumps({"type": "item.completed", "item": {
            "id": "i%d" % number, "type": "command_execution", "command": "/bin/zsh -lc '%s'" % text,
            "aggregated_output": rows[number][1], "exit_code": rows[number][0],
            "status": "completed"}}) + "\n" for number, text in enumerate(commands, 1)]
        facts = {"commands": commands, "tokens": tokens,
                 "baseline": {"env_names": 10, "ps_lines": 5, "lsof": 1}}
        return self.module.judge(lines, facts)

    def test_judge_passes_the_hand_made_fixture(self):
        self.assertEqual(self.judged(), [])

    def test_judge_fails_an_env_that_printed_no_name(self):
        self.assertEqual(self.judged(c7=(1, "")),
                         [("env", "no name printed (the command gave no output)")])

    def test_judge_fails_a_ps_that_printed_nothing(self):
        self.assertEqual([check for check, _ in self.judged(c8=(1, ""))], ["ps"])

    def test_judge_fails_an_lsof_that_printed_nothing(self):
        self.assertEqual(self.judged(c9=(1, "")), [("lsof", "count '', baseline 1")])

    def test_a_judge_run_of_a_saved_stream_with_no_env_name_exits_1_with_the_line(self):
        paths = {"S": "/x/s", "H": "/x/h", "T": "/x/t", "Q": "/x/q", "K": "/x/k"}
        commands = self.module.commands_of(paths)
        tokens = dict((name, name.lower() * 8) for name in "KSHTQI")
        rows = [(0, tokens["I"] + "\n")] + [(1, "cat: x: Operation not permitted\n")] * 5 + [
            (1, ""), (0, "ps: Operation not permitted\n"), (0, "1\n")]
        stream = os.path.join(self.base, "stream.jsonl")
        with open(stream, "w", encoding="utf-8") as handle:
            for number, (text, row) in enumerate(zip(commands, rows), 1):
                handle.write(json.dumps({"type": "item.completed", "item": {
                    "id": "i%d" % number, "type": "command_execution", "command": text,
                    "aggregated_output": row[1], "exit_code": row[0],
                    "status": "completed"}}) + "\n")
        with open(os.path.join(self.base, "facts.json"), "w", encoding="utf-8") as handle:
            json.dump({"version": VERSION, "commands": commands, "tokens": tokens,
                       "baseline": {"env_names": 10, "ps_lines": 5, "lsof": 1}}, handle)
        code, out = self.run_script(("--judge", stream))
        self.assertEqual(code, 1, out)
        self.assertIn("R19 FAIL: env: no name printed (the command gave no output)", out)

    def test_judge_refuses_a_stream_with_no_facts_beside_it(self):
        path = os.path.join(self.base, "stream.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        code, out = self.run_script(("--judge", path))
        self.assertEqual(code, 2)
        self.assertIn("R19 REFUSED: cannot read the saved stream and the facts.json", out)


if __name__ == "__main__":
    unittest.main()
