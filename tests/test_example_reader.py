"""Tests for examples/readers/model_reader.py and the first A/B plan. All data here is invented.

No test starts a real model. A fake `codex` or `claude` is a small Python script in a temp
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

def json_dump(value):
    import json
    return json.dumps(value)


FAKE = '''#!%(python)s
import json, os, sys
args = sys.argv[1:]
log = os.path.join(%(fake_dir)r, "%(name)s.call.json")
stdin = sys.stdin.read()
call = {"args": args, "stdin": stdin, "cwd": os.getcwd(), "listing": os.listdir(os.getcwd())}
with open(log, "w") as handle:
    json.dump(call, handle)
with open(os.path.join(%(fake_dir)r, "%(name)s.calls.jsonl"), "a") as handle:
    handle.write(json.dumps(call) + "\\n")
if "--output-format" in args:
    kind = os.environ.get("FAKE_CLAUDE_INIT", "zero")
    with open(os.path.join(os.getcwd(), "preflight-marker.txt"), "w") as handle:
        handle.write("written by the fake preflight")
    if kind == "hang":
        import subprocess, time
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        with open(os.path.join(%(fake_dir)r, "child.pid"), "w") as handle:
            handle.write(str(child.pid))
        time.sleep(300)
    init = {"type": "system", "subtype": "init", "mcp_servers": [], "tools": []}
    if kind == "server":
        init["mcp_servers"] = [{"name": "invented-server", "status": "connected"}]
    elif kind == "tool":
        init["tools"] = ["invented_tool"]
    elif kind == "nokeys":
        del init["mcp_servers"]
    elif kind == "notools":
        del init["tools"]
    if kind == "garbage":
        sys.stdout.write("this is not json\\nneither is this\\n")
    elif kind != "empty":
        sys.stdout.write(json.dumps({"type": "other"}) + "\\n" + json.dumps(init) + "\\n")
    sys.stdout.flush()
    sys.exit(0)
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

    def calls(self, name):
        import json
        path = os.path.join(self.fake_dir, name + ".calls.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as handle:
            return [json.loads(line) for line in handle if line.strip()]

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

    def load_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("model_reader_claude_test", READER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_claude_by_argument_runs_the_fake_claude_and_prints_its_reply(self):
        self.fake("claude")
        self.fake("codex")
        before = self.listing()
        code, out, err = self.run_reader("claude")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, REPLY)
        call = self.call("claude")
        for text in FILES.values():
            self.assertIn(text, call["stdin"])
        self.assertLess(call["stdin"].index("invented prompt text"),
                        call["stdin"].index("invented version alpha"))
        self.assertLess(call["stdin"].index("invented version alpha"),
                        call["stdin"].index("invented version beta"))
        self.assertFalse(os.path.exists(os.path.join(self.fake_dir, "codex.call.json")))
        self.assertEqual(self.listing(), before)

    A_PRIME = ["-p", "--restricted", "--strict-mcp-config", "--tools", "", "--setting-sources", "",
               "--no-session-persistence"]

    def test_check_init_passes_a_zero_zero_event(self):
        module = self.load_module()
        lines = ['{"type": "other"}\n',
                 '{"type": "system", "subtype": "init", "mcp_servers": [], "tools": []}\n']
        self.assertEqual(module.check_init(lines), (0, 0))

    def assert_check_init_refuses(self, lines):
        module = self.load_module()
        with self.assertRaises(module.ReaderError) as ctx:
            module.check_init(lines)
        self.assertEqual(ctx.exception.code, 2)
        self.assertTrue(str(ctx.exception).startswith("claude preflight refused"))
        self.assertNotIn("invented", str(ctx.exception))

    def test_check_init_refuses_a_server(self):
        self.assert_check_init_refuses(['{"type": "system", "subtype": "init", '
                                        '"mcp_servers": [{"name": "invented"}], "tools": []}'])

    def test_check_init_refuses_a_tool(self):
        self.assert_check_init_refuses(['{"type": "system", "subtype": "init", '
                                        '"mcp_servers": [], "tools": ["invented"]}'])

    def test_check_init_refuses_a_missing_server_key(self):
        self.assert_check_init_refuses(['{"type": "system", "subtype": "init", "tools": []}'])

    def test_check_init_refuses_a_missing_tools_key(self):
        self.assert_check_init_refuses(['{"type": "system", "subtype": "init", "mcp_servers": []}'])

    def test_check_init_refuses_a_key_that_is_not_a_list(self):
        self.assert_check_init_refuses(['{"type": "system", "subtype": "init", '
                                        '"mcp_servers": null, "tools": []}'])

    def test_check_init_refuses_unparseable_lines(self):
        self.assert_check_init_refuses(["not json\n", "{broken\n"])

    def test_check_init_refuses_no_lines(self):
        self.assert_check_init_refuses([])

    def test_a_zero_preflight_then_the_real_call_in_order_in_empty_folders(self):
        module = self.load_module()
        self.fake("claude")
        code, out, err = self.run_reader("claude", FAKE_CLAUDE_INIT="zero")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, REPLY)
        pre, real = self.calls("claude")
        self.assertIn("--output-format", pre["args"])
        self.assertIn("stream-json", pre["args"])
        self.assertEqual(pre["args"][:len(module.CLAUDE_RESTRICT) + 1],
                         ["-p", *module.CLAUDE_RESTRICT])
        self.assertEqual(pre["args"][-1], "Reply with the word ready.")
        self.assertEqual(pre["stdin"], "")
        self.assertEqual(real["args"], self.A_PRIME)
        self.assertIn("invented version beta", real["stdin"])
        for call in (pre, real):
            self.assertEqual(call["listing"], [])
            self.assertNotEqual(os.path.realpath(call["cwd"]), os.path.realpath(self.folder))

    def test_the_preflight_and_the_real_call_use_different_folders(self):
        self.fake("claude")
        code, _out, err = self.run_reader("claude", FAKE_CLAUDE_INIT="zero")
        self.assertEqual((code, err), (0, ""))
        pre, real = self.calls("claude")
        self.assertIn("--output-format", pre["args"])
        self.assertNotEqual(os.path.realpath(pre["cwd"]), os.path.realpath(real["cwd"]))
        self.assertEqual(real["listing"], [])
        for call in (pre, real):
            self.assertNotEqual(os.path.realpath(call["cwd"]), os.path.realpath(self.folder))

    def test_a_preflight_that_hangs_ends_at_the_deadline_and_leaves_no_descendant(self):
        import time
        self.fake("claude")
        shim = os.path.join(self._tmp.name, "shim.py")
        with open(shim, "w") as handle:
            handle.write("import runpy, sys\n"
                         "sys.argv = [sys.argv[1]]\n"
                         "import importlib.util\n"
                         "spec = importlib.util.spec_from_file_location('mr', sys.argv[0])\n"
                         "mod = importlib.util.module_from_spec(spec)\n"
                         "spec.loader.exec_module(mod)\n"
                         "mod.PREFLIGHT_WAIT = 1.0\n"
                         "try:\n"
                         "    sys.exit(mod.main(['claude'], __import__('os').environ, __import__('os').getcwd()))\n"
                         "except mod.ReaderError as exc:\n"
                         "    sys.stderr.write('model_reader: %s\\n' % exc)\n"
                         "    sys.exit(exc.code)\n")
        start = time.monotonic()
        proc = subprocess.run([sys.executable, "-I", shim, READER], cwd=self.folder,
                              env={"PATH": self.fake_dir, "FAKE_CLAUDE_INIT": "hang"},
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=60)
        elapsed = time.monotonic() - start
        err = proc.stderr.decode("utf-8")
        self.assertEqual((proc.returncode, proc.stdout), (2, b""), err)
        self.assertIn("claude preflight refused: no readable init event", err)
        self.assertLess(elapsed, 15)
        calls = self.calls("claude")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("invented prompt text", json_dump(calls))
        with open(os.path.join(self.fake_dir, "child.pid")) as handle:
            pid = int(handle.read())
        gone = False
        end = time.monotonic() + 3
        # Known limit: this polls a grandchild's pid against a deadline; without a pid-file
        # handshake with the fake it cannot be made free of sleeps.
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                gone = True
                break
            time.sleep(0.1)
        if not gone:
            os.kill(pid, 9)
        self.assertTrue(gone, "the fake's descendant survived the preflight")

    def stopped_preflight_setup(self, kind="hang"):
        """Load the module, put the fake claude on PATH, and record the Popen it starts."""
        from unittest import mock
        module = self.load_module()
        self.fake("claude")
        started = []
        real_popen = subprocess.Popen

        def recording_popen(*args, **kwargs):
            proc = real_popen(*args, **kwargs)
            started.append(proc)
            return proc

        for patcher in (mock.patch.dict(os.environ, {"PATH": self.fake_dir,
                                                     "FAKE_CLAUDE_INIT": kind}),
                        mock.patch.object(module.subprocess, "Popen", recording_popen)):
            patcher.start()
            self.addCleanup(patcher.stop)

        def reap():
            for proc in started:
                try:
                    os.killpg(proc.pid, 9)
                except OSError:
                    pass
                proc.wait()
            path = os.path.join(self.fake_dir, "child.pid")
            if os.path.exists(path):
                with open(path) as handle:
                    try:
                        os.kill(int(handle.read()), 9)
                    except (OSError, ValueError):
                        pass
        self.addCleanup(reap)
        return module, started

    def test_a_failure_right_after_the_process_starts_still_stops_it(self):
        import time
        from unittest import mock
        module, started = self.stopped_preflight_setup()
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(module.threading.Thread, "start",
                                   side_effect=RuntimeError("invented failure")):
                with self.assertRaises(RuntimeError):
                    module.claude_preflight(folder)
        self.assertEqual(len(started), 1)
        self.assertIsNotNone(started[0].poll(), "the fake claude was left running")
        path = os.path.join(self.fake_dir, "child.pid")
        if os.path.exists(path):
            with open(path) as handle:
                pid = int(handle.read())
            end = time.monotonic() + 3
            while time.monotonic() < end:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                self.fail("the fake's descendant survived")
        self.assertNotIn("invented prompt text", json_dump(self.calls("claude")))

    def test_a_thread_that_cannot_start_raises_its_own_error_and_closes_the_pipe(self):
        from unittest import mock
        module, started = self.stopped_preflight_setup()
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(module.threading.Thread, "start",
                                   side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError) as caught:
                    module.claude_preflight(folder)
        self.assertEqual(str(caught.exception), "boom")
        self.assertEqual(len(started), 1)
        self.assertIsNotNone(started[0].poll(), "the fake claude was left running")
        self.assertTrue(started[0].stdout.closed, "the pipe was left open")

    def test_a_group_signal_that_is_refused_falls_back_to_the_leader_and_still_refuses(self):
        from unittest import mock
        module, started = self.stopped_preflight_setup()
        module.PREFLIGHT_WAIT = 1.0
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(module.os, "killpg", side_effect=PermissionError):
                with self.assertRaises(module.ReaderError) as caught:
                    module.claude_preflight(folder)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("claude preflight refused: no readable init event", str(caught.exception))
        self.assertIsNotNone(started[0].poll(), "the leader was left running")
        self.assertNotIn("invented prompt text", json_dump(self.calls("claude")))

    def test_a_leader_that_cannot_be_stopped_is_a_loud_failure(self):
        from unittest import mock
        module = self.load_module()

        class Stuck:
            pid = 1
            def terminate(self): pass
            def kill(self): pass
            def wait(self, timeout=None): pass
            def poll(self): return None

        with mock.patch.object(module.os, "killpg", side_effect=PermissionError):
            with self.assertRaises(module.ReaderError) as caught:
                module._stop_group(Stuck())
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(str(caught.exception),
                         "claude preflight could not stop its process; nothing from the "
                         "read folder was sent")

    def assert_preflight_refuses(self, kind):
        self.fake("claude")
        code, out, err = self.run_reader("claude", FAKE_CLAUDE_INIT=kind)
        self.assertEqual((code, out), (2, ""), kind)
        self.assertEqual(err.count("\n"), 1, err)
        self.assertTrue(err.startswith("model_reader: claude preflight refused"), err)
        calls = self.calls("claude")
        self.assertEqual(len(calls), 1, kind)
        self.assertIn("--output-format", calls[0]["args"])
        self.assertEqual(calls[0]["stdin"], "")
        self.assertEqual(calls[0]["listing"], [])
        self.assertNotEqual(os.path.realpath(calls[0]["cwd"]), os.path.realpath(self.folder))
        self.assertNotIn("invented prompt text", json_dump(calls))

    def test_preflight_refuses_a_server_and_sends_nothing(self):
        self.assert_preflight_refuses("server")

    def test_preflight_refuses_a_tool_and_sends_nothing(self):
        self.assert_preflight_refuses("tool")

    def test_preflight_refuses_a_missing_server_key_and_sends_nothing(self):
        self.assert_preflight_refuses("nokeys")

    def test_preflight_refuses_a_missing_tools_key_and_sends_nothing(self):
        self.assert_preflight_refuses("notools")

    def test_preflight_refuses_unparseable_output_and_sends_nothing(self):
        self.assert_preflight_refuses("garbage")

    def test_preflight_refuses_no_output_and_sends_nothing(self):
        self.assert_preflight_refuses("empty")

    def test_claude_in_the_environment_works_the_same(self):
        self.fake("claude")
        self.fake("codex")
        code, out, err = self.run_reader(MODEL_READER_CLI="claude")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, REPLY)
        self.assertTrue(os.path.exists(os.path.join(self.fake_dir, "claude.call.json")))
        self.assertFalse(os.path.exists(os.path.join(self.fake_dir, "codex.call.json")))

    def test_the_claude_argv_is_exactly_the_restricted_list_with_the_message_on_stdin(self):
        module = self.load_module()
        self.fake("claude")
        code, _out, err = self.run_reader("claude")
        self.assertEqual((code, err), (0, ""))
        call = self.call("claude")
        self.assertEqual(call["args"], ["-p", *module.CLAUDE_RESTRICT, "--no-session-persistence"])
        self.assertEqual(call["args"], ["-p", "--restricted", "--strict-mcp-config", "--tools", "",
                                        "--setting-sources", "", "--no-session-persistence"])
        self.assertIn("invented version beta", call["stdin"])

    def test_bare_is_not_passed_even_when_an_api_key_is_set(self):
        """Checks the argv, not the environment; it says nothing about which credentials the run uses."""
        self.fake("claude")
        code, _out, err = self.run_reader("claude", ANTHROPIC_API_KEY="invented-not-a-key")
        self.assertEqual((code, err), (0, ""))
        self.assertNotIn("--bare", self.call("claude")["args"])

    def test_the_claude_argv_has_no_apps_override(self):
        self.fake("claude")
        self.run_reader("claude")
        self.assertNotIn("--disable", self.call("claude")["args"])

    def test_the_argument_beats_the_environment(self):
        self.fake("claude")
        self.fake("codex")
        code, _out, _err = self.run_reader("claude", MODEL_READER_CLI="codex")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(self.fake_dir, "claude.call.json")))
        self.assertFalse(os.path.exists(os.path.join(self.fake_dir, "codex.call.json")))

    def test_an_unknown_name_says_use_codex_or_claude(self):
        code, out, err = self.run_reader("gemini")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "model_reader: unknown CLI 'gemini': use codex or claude\n")

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
        self.assertIn("use codex or claude", err)

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
