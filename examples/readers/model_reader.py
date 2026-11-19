#!/usr/bin/env python3
"""An example reader for `track-record ab` and `track-record panel`: it asks a model CLI to
read one folder.

This file is an example, not part of the installed package. It is the one place a
reader's behaviour is spelled out, so you can read it, change it or replace it.

How it works. `track-record ab run --live` and `track-record panel run --live` start this
program once per read, with the read folder as its working folder. An ab folder holds
PROMPT.txt, POSTING.txt, A.txt and B.txt. A panel folder holds PROMPT.txt, POSTING.txt,
LENS.txt and DOCUMENT.txt. The reader tells them apart by the files present and refuses a
folder that is neither (exit status 2, one line on standard error). It reads the four files
(and writes nothing), pastes them into one message, hands the message to a model CLI on
standard input, and prints the model's reply on standard output. The tool scores that reply;
the reply format is in PROMPT.txt.

Which CLI: the first argument, or the environment variable MODEL_READER_CLI, either
`codex` (the default) or `claude`. In a plan, the reader line carries the argument. For an
ab plan:

    reader-1 | python3 /full/path/to/model_reader.py claude | cost 1 | family claude

For a panel plan, whose reader lines take `not-blind`, `cost <n>` and `reader-group <name>`
and no `family`:

    reader-1 | python3 /full/path/to/model_reader.py claude | cost 1

Where the model command starts. Neither CLI starts in the read folder: each starts in a fresh
folder made with the system's temporary-folder function and removed afterwards (except when the
tool stops the reader at its read timeout), whose path carries nothing of the plan. For codex
that folder holds byte-for-byte copies of the four files and no other file; for claude the
preflight and the call each start in an empty folder of their own. While a model command runs,
the reader's own working folder is a fresh empty folder as well, because `lsof` lists the
working folder of every process of yours.

The exact commands, with the message on standard input:

    codex exec --skip-git-repo-check --ephemeral --ignore-user-config --disable apps
        --color never -c approval_policy="never" -c default_permissions="reader"
        -c permissions.reader.filesystem={":minimal"="read",
        ":workspace_roots"={"."="read"}, ":slash_tmp"="none", ":tmpdir"="none",
        "<install folder>"="read"}
        -c shell_environment_policy.inherit=none --output-last-message <temp file> -
    claude -p --restricted --strict-mcp-config --tools "" --setting-sources ""
        --no-session-persistence

codex never asks for approval, saves no session, and only the final message is used (taken
from the temp file, not from what codex prints). The permissions.reader.filesystem profile
lets the commands the model runs read the folder codex starts in, the system's own files and
the folder codex is installed in, and refuses /tmp and the folder TMPDIR names. The
shell_environment_policy.inherit=none entry cuts the environment of those commands. codex
itself is started with an environment built from nothing: PATH (the install folder, then
/usr/bin and /bin), HOME and TMPDIR (the folder that holds the reply file), and no other
variable. The install folder is the folder that holds the `codex` program as PATH finds it,
with links in that folder's path followed. The reader refuses to start codex, with exit
status 2, when that folder is too wide to grant: `/`, `/usr`, `/usr/local`, `/opt`,
`/opt/homebrew`, your home folder or a folder that holds it, or a folder that holds the read
folder or the folder codex starts in. A codex whose sign-in is in a folder named by
CODEX_HOME, or that needs a variable such as a proxy setting, fails the read under this
environment. Whether codex applies the profile to the commands its own model issues has not
been measured in a live run, and the profile does not hide the arguments or the environment
of your other processes.
`--disable apps` (the same as `-c features.apps=false`) turns codex's apps and connectors
feature off, so the connectors of your account are not meant to be offered to it. That the
tools are gone from a `codex exec` run has not been measured: a tool roster taken from
`codex app-server` under the same flag is the only measurement, and it is not an `exec` run.
codex uses your own logged-in CLI, so it
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
CLI name is not one of the two, a read-folder file is missing, the folder is of neither kind,
a folder cannot be made or codex is installed in a folder that is too wide to grant; 1 if the
CLI fails or returns nothing. A one-line reason goes to standard error. Python 3.9 or later, standard
library only.
"""

import contextlib
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

try:
    import pwd
except ImportError:  # no system list of users, as on Windows
    pwd = None

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
# The two files every read folder holds, in the order they are read.
COMMON = (("PROMPT.txt", "the instructions"), ("POSTING.txt", "the job posting"))
# The two files that tell the kinds of folder apart, and what is pasted, by kind.
KINDS = {
    "ab": (("A.txt", "version A"), ("B.txt", "version B")),
    "panel": (("LENS.txt", "the role to read in"), ("DOCUMENT.txt", "the document to read")),
}
# The names in the order the refusal lists them.
KIND_NAMES = ("A.txt", "B.txt", "DOCUMENT.txt", "LENS.txt")
PASTE_NOTE = (
    "The four files named in the instructions are pasted below, because you cannot open "
    "files. Treat each block as that file. Reply in the format the instructions give.\n"
)

# The folders that codex may never be installed in, because the profile reads its install
# folder in full (those folders themselves, not folders below them).
TOO_WIDE = ("/", "/usr", "/usr/local", "/opt", "/opt/homebrew")
# The profile entries before the install folder: the system's own files, the folder codex
# starts in, and neither /tmp nor the folder TMPDIR names.
PROFILE_HEAD = ('{":minimal"="read", ":workspace_roots"={"."="read"}, '
                '":slash_tmp"="none", ":tmpdir"="none", ')


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


def read_file(folder, name):
    """The bytes of one read-folder file; exit status 2 with the system's own words if it
    cannot be read."""
    try:
        with open(os.path.join(folder, name), "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise ReaderError("cannot read %s in the read folder: %s"
                          % (name, exc.strerror or exc), 2)


def names_present(folder):
    """The names among A.txt, B.txt, DOCUMENT.txt and LENS.txt that the folder has an entry of."""
    return [name for name in KIND_NAMES if os.path.lexists(os.path.join(folder, name))]


def kind_of_folder(folder):
    """`ab`, `panel` or `neither`, by which names are present."""
    found = names_present(folder)
    ab = [n for n in found if n in ("A.txt", "B.txt")]
    panel = [n for n in found if n in ("DOCUMENT.txt", "LENS.txt")]
    if ab and not panel:
        return "ab"
    if panel and not ab:
        return "panel"
    return "neither"


def read_folder(folder):
    """Read the folder: PROMPT.txt, then POSTING.txt, then the kind, then the kind's two files.
    Returns the (name, what, bytes) of the four files in the order they are read."""
    files = [(name, what, read_file(folder, name)) for name, what in COMMON]
    kind = kind_of_folder(folder)
    if kind == "neither":
        found = ", ".join(names_present(folder)) or "none of them"
        raise ReaderError("cannot tell which kind of read folder this is: an ab folder holds "
                          "A.txt and B.txt, a panel folder holds DOCUMENT.txt and LENS.txt, "
                          "and this one holds %s" % found, 2)
    files += [(name, what, read_file(folder, name)) for name, what in KINDS[kind]]
    return kind, files


def build_message(kind, files):
    """The note, then a block for each file: PROMPT, POSTING, A, B for ab; PROMPT, LENS,
    POSTING, DOCUMENT for panel (the order the panel's PROMPT.txt says to read in)."""
    by_name = {name: (what, data) for name, what, data in files}
    order = (("PROMPT.txt", "POSTING.txt") + tuple(n for n, _ in KINDS[kind]) if kind == "ab"
             else ("PROMPT.txt", "LENS.txt", "POSTING.txt", "DOCUMENT.txt"))
    parts = [PASTE_NOTE]
    for name in order:
        what, data = by_name[name]
        text = data.decode("utf-8")
        parts.append("\n===== %s (%s) =====\n%s\n" % (name, what, text.rstrip("\n")))
    return "".join(parts)


def find_cli(name):
    path = shutil.which(name)
    if path is None:
        raise ReaderError("%s is not installed or not on PATH" % name, 2)
    return path


def locate_cli(name):
    """Where PATH finds the program, made absolute, or None. Called before the reader changes
    its working folder, so a relative PATH entry resolves from the read folder as it always
    did; the error for None is raised by need_cli where the program is first needed."""
    path = shutil.which(name)
    return None if path is None else os.path.abspath(path)


def need_cli(name, program):
    if program is None:
        raise ReaderError("%s is not installed or not on PATH" % name, 2)
    return program


def run_cli(args, message, cwd=None, env=None):
    try:
        done = subprocess.run(args, input=message.encode("utf-8"), cwd=cwd, env=env,
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


def claude_preflight(cwd, program=None):
    # The same flags on a fixed prompt. Stdout is read until the init event, a deadline or the
    # end of the stream, then the whole process group is stopped. The raw stream is not
    # printed, saved or put in an error message.
    args = [program or find_cli("claude"), "-p", *CLAUDE_RESTRICT, "--no-session-persistence",
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


def ask_claude(message, program):
    # Tools, MCP servers and settings files are restricted by CLAUDE_RESTRICT; no session is
    # saved. The reader adds neither `--bare` nor an API key; it inherits your environment, so
    # it uses whatever sign-in `claude` finds there. The check in the module docstring ran on
    # a machine where the init event reported no API key (`apiKeySource` `none`). The
    # preflight runs first in its own fresh empty folder; the message is not sent until it
    # returns, and the real call runs in a second fresh empty folder.
    # Both folders are made by make_folder() before any claude process starts, so a folder
    # that cannot be made starts no model command, and both are removed on every exit.
    with contextlib.ExitStack() as stack:
        pre = make_folder()
        stack.callback(shutil.rmtree, pre, True)
        real = make_folder()
        stack.callback(shutil.rmtree, real, True)
        claude_preflight(pre, need_cli("claude", program))
        args = [program, "-p", *CLAUDE_RESTRICT, "--no-session-persistence"]
        return run_cli(args, message, cwd=real).stdout.decode("utf-8", "replace")


def make_folder():
    """A fresh empty folder under the system's temporary folder, named by nothing of the plan."""
    try:
        return os.path.abspath(tempfile.mkdtemp())
    except OSError as exc:
        raise ReaderError("cannot run: could not make the reader's folder: %s"
                          % (exc.strerror or exc), 2)


def make_codex_folder(folder_files):
    """A fresh folder holding a byte-for-byte copy of each (name, bytes) and no other file.
    On failure it removes what it made and raises the exit-2 error."""
    folder = make_folder()
    try:
        for name, data in folder_files:
            with open(os.path.join(folder, name), "wb") as handle:
                handle.write(data)
    except OSError as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise ReaderError("cannot run: could not make the reader's folder: %s"
                          % (exc.strerror or exc), 2)
    return folder


def _real(path):
    return os.path.realpath(path)


def _within(inner, outer):
    """True when `inner` is `outer` or lies below it (both are compared by real path)."""
    inner, outer = _real(inner), _real(outer)
    try:
        return os.path.commonpath([inner, outer]) == outer
    except ValueError:
        return False


def home_folders(environ):
    """The home folder named by HOME when it is set and not empty, and the one the system
    lists for the user; either may be missing."""
    named = environ.get("HOME") or None
    listed = None
    if pwd is not None:
        try:
            listed = pwd.getpwuid(os.getuid()).pw_dir or None
        except KeyError:
            listed = None
    return named, listed


def check_install_folder(install_folder, read_folder, start_folder, environ=None):
    """Refuse (exit status 2) an install folder that is too wide to grant: `/`, `/usr`,
    `/usr/local`, `/opt`, `/opt/homebrew` themselves, a home folder or a folder that holds
    one, or a folder that holds the read folder or the folder codex starts in."""
    environ = os.environ if environ is None else environ
    install = _real(install_folder)
    wide = install in [_real(folder) for folder in TOO_WIDE]
    for home in home_folders(environ):
        if home and _within(home, install):
            wide = True
    for held in (read_folder, start_folder):
        if _within(held, install):
            wide = True
    if wide:
        raise ReaderError("cannot run: codex is installed under %s, which is too wide to "
                          "grant; install codex in a folder of its own and run again"
                          % install, 2)


def codex_profile(install_folder):
    """The value of the permissions.reader.filesystem entry: the install folder is readable."""
    quoted = install_folder.replace("\\", "\\\\").replace('"', '\\"')
    return PROFILE_HEAD + '"%s"="read"}' % quoted


def codex_args(install_folder, reply_path):
    """The arguments after the codex program, one list: the permission profile is chosen with
    the `-c` entries default_permissions and permissions.reader.filesystem, and the shell
    environment of the model's commands is cut with shell_environment_policy.inherit=none."""
    return ["exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
            *CODEX_APPS_OFF, "--color", "never",
            "-c", 'approval_policy="never"',
            "-c", 'default_permissions="reader"',
            "-c", "permissions.reader.filesystem=" + codex_profile(install_folder),
            "-c", "shell_environment_policy.inherit=none",
            "--output-last-message", reply_path, "-"]


def codex_env(install_folder, home, tmpdir):
    """The environment codex starts with, built from nothing: PATH, HOME and TMPDIR only."""
    return {"PATH": install_folder + ":/usr/bin:/bin", "HOME": home, "TMPDIR": tmpdir}


def ask_codex(message, files, read_dir, environ, stack, found):
    # codex starts in a fresh folder of four copies, under a read-only permission profile,
    # with an environment of three names. Only the final message is used: it is taken from a
    # file in a fresh folder of its own (the folder TMPDIR names), not from standard output,
    # because codex prints progress there. The read folder is never written.
    program = need_cli("codex", found)
    install = _real(os.path.dirname(program))
    start = make_codex_folder([(name, data) for name, _what, data in files])
    stack.callback(shutil.rmtree, start, True)
    scratch = make_folder()
    stack.callback(shutil.rmtree, scratch, True)
    check_install_folder(install, read_dir, start, environ)
    named, listed = home_folders(environ)
    home = named or listed
    if not home:
        raise ReaderError("cannot run: no home folder: HOME is not set and the system lists "
                          "none", 2)
    reply_path = os.path.join(scratch, "reply.txt")
    run_cli([program] + codex_args(install, reply_path), message, cwd=start,
            env=codex_env(install, home, scratch))
    try:
        with open(reply_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        raise ReaderError("codex wrote no reply")


def main(argv, environ, folder):
    name = choose_cli(argv, environ)
    kind, files = read_folder(folder)
    message = build_message(kind, files)
    # Resolved here, before the working folder changes: see locate_cli.
    program = locate_cli(name)
    with contextlib.ExitStack() as stack:
        # The reader's own working folder is a fresh empty folder while a model command runs,
        # so that a process listing does not show the read folder. Callbacks run last-in
        # first-out: the working folder is restored, then the fresh folder is removed.
        fresh = make_folder()
        stack.callback(shutil.rmtree, fresh, True)
        original = os.getcwd()
        try:
            os.chdir(fresh)
        except OSError as exc:
            raise ReaderError("cannot run: could not make the reader's folder: %s"
                              % (exc.strerror or exc), 2)
        stack.callback(_back_to, original)
        reply = (ask_codex(message, files, folder, environ, stack, program) if name == "codex"
                 else ask_claude(message, program))
    if not reply.strip():
        raise ReaderError("%s returned an empty reply" % name)
    sys.stdout.buffer.write((reply.rstrip("\n") + "\n").encode("utf-8"))
    sys.stdout.flush()
    return 0


def _back_to(path):
    try:
        os.chdir(path)
    except OSError:
        # The folder the reader started in is gone; there is nothing to go back to.
        pass


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:], os.environ, os.getcwd()))
    except ReaderError as exc:
        sys.stderr.write("model_reader: %s\n" % exc)
        sys.exit(exc.code)
