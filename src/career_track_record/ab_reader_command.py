"""Run a reader command: the one place that starts a reader program.

A reader command is the one outside program a user names for ``track-record ab``. This
module starts it with an argument list and never with a shell, in exactly one call.
"""

import subprocess


class ReaderCommandError(Exception):
    """The reader command could not be run. ``reason`` is "not found", "timed out"
    or "failed"."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


def run_reader_command(args, folder, timeout):
    """Run ``args`` (a list of str) with ``folder`` as its working folder.

    Returns the finished process, so the caller can read its return code and output.
    A program that exits with a non-zero code is not an error here."""
    if not (isinstance(args, list) and args and all(isinstance(a, str) for a in args)):
        raise TypeError("the reader command must be a non-empty list of str")
    try:
        done = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=timeout, check=False, cwd=folder)
    except FileNotFoundError:
        raise ReaderCommandError("not found")
    except subprocess.TimeoutExpired:
        raise ReaderCommandError("timed out")
    except OSError:
        raise ReaderCommandError("failed")
    return done
