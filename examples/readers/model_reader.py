#!/usr/bin/env python3
"""An example reader for `track-record ab`: it asks a model CLI to read one pair.

This file is an example, not part of the installed package. It is the one place a
reader's behaviour is spelled out, so you can read it, change it or replace it.

How it works. `track-record ab run --live` starts this program once per read, with the
read folder as its working folder. The folder holds PROMPT.txt, POSTING.txt, A.txt and
B.txt. This program reads those four files (and writes nothing), pastes them into one
message, hands the message to a model CLI on standard input, and prints the model's
reply on standard output. The tool scores that reply; the reply format is in PROMPT.txt.

Which CLI: `codex`, the default; the first argument or the environment variable
MODEL_READER_CLI may name it too. In a plan, the reader line names this script:

    reader-1 | python3 /full/path/to/model_reader.py | cost 1 | family codex

The exact command, with the message on standard input:

    codex exec --sandbox read-only --skip-git-repo-check --ephemeral --ignore-user-config
        --disable apps --color never -c approval_policy="never"
        --output-last-message <temp file> -

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

Exit status: 0 with the reply on standard output; 2 if codex is not installed, the CLI
name is not `codex`, or a read-folder file is missing; 1 if codex fails or returns
nothing. A one-line reason goes to standard error. Python 3.9 or later, standard
library only.
"""

import os
import shutil
import subprocess
import sys
import tempfile

ENV_VAR = "MODEL_READER_CLI"
# Turns codex's apps and connectors feature off (`codex exec --help`: `--disable <FEATURE>` is
# equivalent to `-c features.<name>=false`). One value, so a tool that lists codex's tools can
# read the same argument the reader sends.
CODEX_APPS_OFF = ("--disable", "apps")
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
    if name == "claude":
        raise ReaderError("the claude option was removed in 0.10.5: with its flags and no API key, "
                          "Claude Code 2.1.327 offered the reader 29 connector tools (measured "
                          "once; 0 with --strict-mcp-config). A `claude -p` reader of your own "
                          "must exclude connectors; see docs/guides/ab.md.", 2)
    if name != "codex":
        raise ReaderError("unknown CLI %r: use codex" % name, 2)
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


def run_cli(args, message):
    try:
        done = subprocess.run(args, input=message.encode("utf-8"),
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
    choose_cli(argv, environ)
    message = build_message(folder)
    reply = ask_codex(message)
    if not reply.strip():
        raise ReaderError("codex returned an empty reply")
    sys.stdout.buffer.write((reply.rstrip("\n") + "\n").encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:], os.environ, os.getcwd()))
    except ReaderError as exc:
        sys.stderr.write("model_reader: %s\n" % exc)
        sys.exit(exc.code)
