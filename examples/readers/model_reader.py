#!/usr/bin/env python3
"""An example reader for `track-record ab`: it asks a model CLI to read one pair.

This file is an example, not part of the installed package. It is the one place a
reader's behaviour is spelled out, so you can read it, change it or replace it.

How it works. `track-record ab run --live` starts this program once per read, with the
read folder as its working folder. The folder holds PROMPT.txt, POSTING.txt, A.txt and
B.txt. This program reads those four files (and writes nothing), pastes them into one
message, hands the message to a model CLI on standard input, and prints the model's
reply on standard output. The tool scores that reply; the reply format is in PROMPT.txt.

Which CLI: the first argument, or the environment variable MODEL_READER_CLI, either
`codex` (the default) or `claude`. In a plan, the reader line carries the argument:

    reader-1 | python3 /full/path/to/model_reader.py claude | cost 1 | family claude

The exact commands, with the message on standard input:

    codex exec --sandbox read-only --skip-git-repo-check --ephemeral --ignore-user-config
        --disable apps --color never -c approval_policy="never"
        --output-last-message <temp file> -
    claude -p --restricted --strict-mcp-config --tools "" --setting-sources ""
        --no-session-persistence

codex runs in a read-only sandbox, never asks for approval, saves no session, and only the
final message is used (taken from the temp file, not from what codex prints). `--disable apps`
(the same as `-c features.apps=false`) turns codex's apps and connectors feature off, so the
connectors of your account are not meant to be offered to it. That the
tools are gone from a `codex exec` run has not been measured: a tool roster taken from
`codex app-server` under the same flag is the only measurement, and it is not an `exec` run.
codex's read-only sandbox stops it changing files. It uses your own logged-in CLI, so it
inherits your account and its settings; if those tell the model who you are, mark the reader
`not-blind` in the plan. `--ignore-user-config` skips codex's config.toml only: codex still
reads the AGENTS.md in your codex home folder, and none of the settings tried in codex 0.156.1
turns that off (checked with `codex debug prompt-input`, without a model call). So the reader
may know who you are; docs/guides/ab.md says what to do.

For claude, the reader adds neither `--bare` nor an API key; it inherits your environment,
so it uses whatever sign-in `claude` finds there. The check below ran on a machine where the
init event reported no API key (`apiKeySource` `none`).
Before it sends your text, the reader runs the same flags once on a fixed harmless prompt
and reads the session's init event; if the event lists any MCP server or any tool, or it
cannot read one, the reader stops with exit status 2 and sends none of the read folder's text.
The preflight and the real run each start in their own fresh empty folder the reader
creates, because a folder holding a project `.mcp.json` has not been measured. In one check of Claude Code 2.1.327, with one
account and an empty folder, the init event listed 0 MCP servers and 0 tools under these
flags. Not measured: the hooks of the plugins that still load, CLAUDE.md and auto-memory,
and the `--bare` and API-key arm. This applies to the `claude` option of this example
reader and is no evidence about any other reader.

Exit status: 0 with the reply on standard output; 2 if the CLI is not installed, the
CLI name is not one of the two, or a read-folder file is missing; 1 if the CLI fails or
returns nothing. A one-line reason goes to standard error. Python 3.9 or later, standard
library only.
"""

import os
import shutil
import json
import signal
import subprocess
import sys
import tempfile
import threading
import time
from queue import Empty, Queue

CLIS = ("codex", "claude")
ENV_VAR = "MODEL_READER_CLI"
# Turns codex's apps and connectors feature off (`codex exec --help`: `--disable <FEATURE>` is
# equivalent to `-c features.<name>=false`). One value, so a tool that lists codex's tools can
# read the same argument the reader sends.
CODEX_APPS_OFF = ("--disable", "apps")
# The flags the claude command carries between `-p` and `--no-session-persistence`, in one
# value so a test can read the same list the reader sends. No `--bare` is passed.
CLAUDE_RESTRICT = ("--restricted", "--strict-mcp-config", "--tools", "", "--setting-sources", "")
# The fixed harmless prompt the claude preflight sends, before any of your text.
PREFLIGHT_PROMPT = "Reply with the word ready."
# Seconds the preflight waits for the init event before it kills the process.
PREFLIGHT_WAIT = 60
# The four files the tool puts in the read folder, in the order they are pasted.
FILES = (
    ("PROMPT.txt", "the instructions"),
    ("POSTING.txt", "the job posting"),
    ("A.txt", "version A"),
    ("B.txt", "version B"),
)
PASTE_NOTE = (
    "The four files named in the instructions are pasted below, because you cannot open "
    "files. Treat each block as that file. Reply in the format the instructions give.\n"
)


class ReaderError(Exception):
    """A read that cannot be answered. ``code`` is the exit status."""

    def __init__(self, message, code=1):
        Exception.__init__(self, message)
        self.code = code


def choose_cli(argv, environ):
    name = argv[0] if argv else environ.get(ENV_VAR, "") or "codex"
    if name not in CLIS:
        raise ReaderError("unknown CLI %r: use codex or claude" % name, 2)
    return name


def build_message(folder):
    parts = [PASTE_NOTE]
    for name, what in FILES:
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except OSError as exc:
            raise ReaderError("cannot read %s in the read folder: %s"
                              % (name, exc.strerror or exc), 2)
        parts.append("\n===== %s (%s) =====\n%s\n" % (name, what, text.rstrip("\n")))
    return "".join(parts)


def find_cli(name):
    path = shutil.which(name)
    if path is None:
        raise ReaderError("%s is not installed or not on PATH" % name, 2)
    return path


def run_cli(args, message, cwd=None):
    try:
        done = subprocess.run(args, input=message.encode("utf-8"), cwd=cwd,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        raise ReaderError("%s could not start: %s" % (os.path.basename(args[0]),
                                                      exc.strerror or exc), 2)
    if done.returncode != 0:
        lines = done.stderr.decode("utf-8", "replace").strip().splitlines()
        why = lines[-1][:200] if lines else "no message"
        raise ReaderError("%s exited with status %d: %s"
                          % (os.path.basename(args[0]), done.returncode, why))
    return done


def _init_event(line):
    """The parsed init event if the line is one, else None."""
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if isinstance(event, dict) and event.get("type") == "system" and event.get("subtype") == "init":
        return event
    return None


def check_init(lines):
    """Fail closed: return (servers, tools) counts if both lists are present and empty.

    Raises ReaderError (exit status 2) otherwise. The message carries counts, no names."""
    for line in lines:
        event = _init_event(line)
        if event is None:
            continue
        servers, tools = event.get("mcp_servers"), event.get("tools")
        if not isinstance(servers, list) or not isinstance(tools, list):
            break
        if servers or tools:
            raise ReaderError("claude preflight refused: the init event listed %d MCP servers "
                              "and %d tools (the measured example, Claude Code 2.1.327, listed "
                              "0 and 0 under these flags); none of the read folder's text was sent"
                              % (len(servers), len(tools)), 2)
        return len(servers), len(tools)
    raise ReaderError("claude preflight refused: no readable init event with an MCP server "
                      "list and a tool list; none of the read folder's text was sent", 2)


def _signal_group(proc, sig):
    # The whole process group when the platform has one, else just the process.
    killpg = getattr(os, "killpg", None)
    try:
        if killpg is not None:
            killpg(proc.pid, sig)
        elif sig == signal.SIGTERM:
            proc.terminate()
        else:
            proc.kill()
    except ProcessLookupError:
        # The group is already gone.
        pass
    except PermissionError:
        # macOS reports EPERM, not ESRCH, for a group that holds nothing but exited processes, so
        # EPERM does not prove the group is gone and does not prove it is alive. Signal the
        # direct child instead; _stop_group then checks that the leader was reaped.
        try:
            if sig == signal.SIGTERM:
                proc.terminate()
            else:
                proc.kill()
        except ProcessLookupError:
            pass


def _stop_group(proc):
    # Terminate, give it at most 2 seconds, then kill. The kill always runs, even when the
    # wait is interrupted; every wait is bounded.
    try:
        _signal_group(proc, signal.SIGTERM)
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    finally:
        _signal_group(proc, getattr(signal, "SIGKILL", signal.SIGTERM))
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    if proc.poll() is None:
        raise ReaderError("claude preflight could not stop its process; nothing from the "
                          "read folder was sent", 2)


def claude_preflight(cwd):
    # The same flags on a fixed prompt. Stdout is read until the init event, a deadline or the
    # end of the stream, then the whole process group is stopped. The raw stream is not
    # printed, saved or put in an error message.
    args = [find_cli("claude"), "-p", *CLAUDE_RESTRICT, "--no-session-persistence",
            "--output-format", "stream-json", "--verbose", PREFLIGHT_PROMPT]
    # Every local is set before the process starts, so the statement after a successful Popen
    # is the try that stops it.
    reader = None
    started = False
    lines = []
    deadline = time.monotonic() + PREFLIGHT_WAIT
    queue = Queue()
    try:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, cwd=cwd, start_new_session=True)
    except OSError as exc:
        raise ReaderError("claude could not start: %s" % (exc.strerror or exc), 2)
    try:
        def pump():
            try:
                for raw in proc.stdout:
                    queue.put(raw)
            except (OSError, ValueError):
                pass
            queue.put(None)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        started = True
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                raw = queue.get(timeout=remaining)
            except Empty:
                break
            if raw is None:
                break
            line = raw.decode("utf-8", "replace")
            lines.append(line)
            if _init_event(line) is not None:
                break
    finally:
        # Runs on every exit, KeyboardInterrupt included.
        try:
            _stop_group(proc)
        finally:
            try:
                if started:
                    # Known limit: a descendant that left the process group can keep the pipe
                    # open, and its reader thread outlives the call.
                    reader.join(timeout=2)
            finally:
                if not started or not reader.is_alive():
                    proc.stdout.close()
    return check_init(lines)


def ask_claude(message):
    # Tools, MCP servers and settings files are restricted by CLAUDE_RESTRICT; no session is
    # saved. The reader adds neither `--bare` nor an API key; it inherits your environment, so
    # it uses whatever sign-in `claude` finds there. The check in the module docstring ran on
    # a machine where the init event reported no API key (`apiKeySource` `none`). The
    # preflight runs first in its own fresh empty folder; the message is not sent until it
    # returns, and the real call runs in a second fresh empty folder.
    with tempfile.TemporaryDirectory() as pre:
        claude_preflight(pre)
    with tempfile.TemporaryDirectory() as real:
        args = [find_cli("claude"), "-p", *CLAUDE_RESTRICT, "--no-session-persistence"]
        return run_cli(args, message, cwd=real).stdout.decode("utf-8", "replace")


def ask_codex(message):
    # Read-only sandbox, approval policy never (no prompts), no saved session, no colour.
    # Only the final message is used: it is taken from a file in a fresh temp folder, not
    # from standard output, because codex prints progress there. The read folder is never
    # written.
    with tempfile.TemporaryDirectory() as scratch:
        reply_path = os.path.join(scratch, "reply.txt")
        args = [find_cli("codex"), "exec", "--sandbox", "read-only", "--skip-git-repo-check",
                "--ephemeral", "--ignore-user-config", *CODEX_APPS_OFF, "--color", "never",
                "-c", 'approval_policy="never"', "--output-last-message", reply_path, "-"]
        run_cli(args, message)
        try:
            with open(reply_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            raise ReaderError("codex wrote no reply")


def main(argv, environ, folder):
    name = choose_cli(argv, environ)
    message = build_message(folder)
    reply = ask_codex(message) if name == "codex" else ask_claude(message)
    if not reply.strip():
        raise ReaderError("%s returned an empty reply" % name)
    sys.stdout.buffer.write((reply.rstrip("\n") + "\n").encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:], os.environ, os.getcwd()))
    except ReaderError as exc:
        sys.stderr.write("model_reader: %s\n" % exc)
        sys.exit(exc.code)
