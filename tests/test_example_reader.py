"""Tests for examples/readers/model_reader.py and the first A/B plan. All data here is invented.

No test starts a real model. A fake `codex` (and a fake `claude`, which must stay uncalled) is a small Python script in a temp
folder that is the only folder on PATH; it records how it was called and prints a canned
reply."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
READER = os.path.join(ROOT, "examples", "readers", "model_reader.py")
EXAMPLES = os.path.join(ROOT, "examples")
REPLY = ("READ: 1\nPRIOR: nothing\nSCORE-A: 6\nSCORE-B: 7\nPREFER: B, slightly\n"
         "DROVE-IT: none\nDOUBTS: none\nUNDERSOLD: none\nOVEREXPLAINED: none\n"
         "OWNED: none\nFLAG-FIXES: none\n")
FILES = {"PROMPT.txt": "invented prompt text", "POSTING.txt": "invented posting text",
         "A.txt": "invented version alpha", "B.txt": "invented version beta"}

REMOVED = ("model_reader: the claude option was removed in 0.10.5: with its flags and no API "
           "key, Claude Code 2.1.327 offered the reader 29 connector tools (measured once; "
           "0 with --strict-mcp-config). A `claude -p` reader of your own must exclude "
           "connectors; see docs/guides/ab.md.\n")

FAKE = '''#!%(python)s
import json, os, sys
args = sys.argv[1:]
log = os.path.join(%(fake_dir)r, "%(name)s.call.json")
with open(log, "w") as handle:
    json.dump({"args": args, "stdin": sys.stdin.read(), "cwd": os.getcwd()}, handle)
if os.path.exists(os.path.join(%(fake_dir)r, "fail")):
    sys.stderr.write("first line\\nboom: not logged in\\n")
    sys.exit(3)
reply = %(reply)r
if "%(name)s" == "codex":
    out = args[args.index("--output-last-message") + 1]
    with open(out, "w") as handle:
        handle.write(reply)
    sys.stdout.write("progress noise, not the reply\\n")
else:
    sys.stdout.write(reply)
'''


@unittest.skipIf(os.name == "nt", "the fake CLIs are POSIX scripts")
class ModelReaderCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fake_dir = os.path.join(self._tmp.name, "bin")
        self.folder = os.path.join(self._tmp.name, "read")
        os.mkdir(self.fake_dir)
        os.mkdir(self.folder)
        for name, text in FILES.items():
            with open(os.path.join(self.folder, name), "w", encoding="utf-8") as handle:
                handle.write(text + "\n")

    def fake(self, name):
        path = os.path.join(self.fake_dir, name)
        with open(path, "w") as handle:
            handle.write(FAKE % {"python": sys.executable, "fake_dir": self.fake_dir,
                                 "name": name, "reply": REPLY})
        os.chmod(path, 0o755)

    def call(self, name):
        import json
        with open(os.path.join(self.fake_dir, name + ".call.json")) as handle:
            return json.load(handle)

    def run_reader(self, *args, **env):
        environ = {"PATH": self.fake_dir}
        environ.update(env)
        proc = subprocess.run([sys.executable, "-I", READER] + list(args), cwd=self.folder,
                              env=environ, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")

    def listing(self):
        return sorted((n, os.path.getmtime(os.path.join(self.folder, n)))
                      for n in os.listdir(self.folder))

    def test_the_prompt_comes_from_prompt_txt_when_stdin_is_empty(self):
        self.fake("codex")
        self.run_reader()
        self.assertIn("invented prompt text", self.call("codex")["stdin"])

    def test_the_reply_is_printed_with_one_final_line_break(self):
        self.fake("codex")
        _code, out, _err = self.run_reader()
        self.assertTrue(out.endswith("FLAG-FIXES: none\n"))
        self.assertFalse(out.endswith("\n\n"))

    def test_codex_is_the_default_and_runs_read_only_with_no_approval(self):
        self.fake("codex")
        for args, env in (((), {}), (("codex",), {}), ((), {"MODEL_READER_CLI": "codex"})):
            code, out, err = self.run_reader(*args, **env)
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(out, REPLY)
            call = self.call("codex")
            self.assertEqual(call["args"][:1], ["exec"])
            self.assertEqual(call["args"][call["args"].index("--sandbox") + 1], "read-only")
            self.assertEqual(call["args"][call["args"].index("-c") + 1],
                             'approval_policy="never"')
            self.assertEqual(call["args"][call["args"].index("--color") + 1], "never")
            self.assertIn("--ephemeral", call["args"])
            self.assertIn("--ignore-user-config", call["args"])
            self.assertIn("--skip-git-repo-check", call["args"])
            self.assertEqual(call["args"][-1], "-")
            self.assertIn("invented version beta", call["stdin"])
        self.assertEqual(sorted(os.listdir(self.folder)), sorted(FILES))

    def test_codex_argv_carries_the_apps_off_override_from_the_module_constant(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("model_reader_under_test", READER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.CODEX_APPS_OFF, ("--disable", "apps"))
        self.fake("codex")
        code, _out, err = self.run_reader("codex")
        self.assertEqual((code, err), (0, ""))
        args = self.call("codex")["args"]
        at = args.index("--disable")
        self.assertEqual(tuple(args[at:at + 2]), module.CODEX_APPS_OFF)
        self.assertEqual(args.count("--disable"), 1)

    def assert_claude_refused(self, *args, **env):
        self.fake("claude")
        self.fake("codex")
        code, out, err = self.run_reader(*args, **env)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, REMOVED)
        self.assertFalse(os.path.exists(os.path.join(self.fake_dir, "claude.call.json")))
        self.assertFalse(os.path.exists(os.path.join(self.fake_dir, "codex.call.json")))

    def test_claude_by_argument_is_refused_and_not_started(self):
        self.assert_claude_refused("claude")

    def test_claude_in_the_environment_is_refused_and_not_started(self):
        self.assert_claude_refused(MODEL_READER_CLI="claude")

    def test_claude_with_an_api_key_is_refused_and_not_started(self):
        self.assert_claude_refused(MODEL_READER_CLI="claude", ANTHROPIC_API_KEY="invented-not-a-key")

    def test_the_argument_beats_the_environment_for_claude_too(self):
        self.assert_claude_refused("claude", MODEL_READER_CLI="codex")

    def test_an_unknown_name_says_use_codex(self):
        code, out, err = self.run_reader("gemini")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "model_reader: unknown CLI 'gemini': use codex\n")

    def test_a_missing_cli_fails_in_one_line(self):
        code, out, err = self.run_reader()
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(err.count("\n"), 1, err)
        self.assertIn("codex", err)
        self.assertIn("not installed or not on PATH", err)

    def test_a_failing_cli_exits_nonzero_with_its_last_stderr_line(self):
        self.fake("codex")
        with open(os.path.join(self.fake_dir, "fail"), "w"):
            pass
        code, out, err = self.run_reader()
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err.count("\n"), 1, err)
        self.assertIn("status 3", err)
        self.assertIn("boom: not logged in", err)

    def test_an_unknown_cli_name_is_refused(self):
        code, out, err = self.run_reader("gpt")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err.count("\n"), 1, err)
        self.assertIn("use codex", err)

    def test_a_missing_read_folder_file_is_refused(self):
        self.fake("codex")
        os.remove(os.path.join(self.folder, "B.txt"))
        code, out, err = self.run_reader()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("B.txt", err)
        self.assertFalse(os.path.exists(os.path.join(self.fake_dir, "codex.call.json")))


class FirstPlanCase(unittest.TestCase):
    """The plan in examples/ freezes and, without --live, prints its commands."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = os.path.join(self._tmp.name, "work")
        shutil.copytree(EXAMPLES, self.work)

    def track(self, *args):
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"),
                   PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-m", "career_track_record"] + list(args),
                              cwd=self.work, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")

    def test_the_plan_freezes_and_run_prints_the_reader_command(self):
        code, out, err = self.track("ab", "freeze", "ab-first-plan.txt")
        # The shipped plan still holds the placeholder path, so freeze warns about it, once.
        self.assertEqual(code, 0, out)
        self.assertEqual(err.count("\n"), 1, err)
        self.assertTrue(err.startswith("warning: reader reader-1: the script does not exist: "
                                       "/path/to/career-track-record/examples/readers/"), err)
        self.assertTrue(os.path.exists(os.path.join(self.work, "ab-first-plan.txt.freeze")))
        code, out, err = self.track("ab", "run", "ab-first-plan.txt")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("model_reader.py (cost 1 per read)", out)
        self.assertIn("planned reads: 12", out)
        self.assertIn("estimated spend: 12", out)
        self.assertFalse(os.path.exists(os.path.join(self.work, "result-1.txt")))

    def test_the_reader_line_names_the_example_reader_and_its_placeholder_path(self):
        with open(os.path.join(EXAMPLES, "ab-first-plan.txt"), encoding="utf-8") as handle:
            plan = handle.read()
        self.assertIn("python3 /path/to/career-track-record/examples/readers/model_reader.py",
                      plan)
        self.assertTrue(os.path.isfile(READER))


if __name__ == "__main__":
    unittest.main()
