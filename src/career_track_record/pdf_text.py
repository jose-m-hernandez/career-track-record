"""Read a PDF's text with the pdftotext program.

This is the only module that starts another program, and it starts exactly one:
``pdftotext FILE -`` in its default (non-layout) mode, or ``pdftotext FILE - -layout``
in its layout mode when ``layout=True`` is given. No shell is used.
"""

import subprocess


class PdfTextError(Exception):
    """pdftotext could not give the text. ``reason`` is "not found" or "failed"."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


def pdf_text(path, timeout=60, *, errors="replace", layout=False):
    try:
        done = subprocess.run(["pdftotext", path, "-", *(["-layout"] if layout else [])],
                              stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError:
        raise PdfTextError("not found")
    except (subprocess.TimeoutExpired, OSError):
        raise PdfTextError("failed")
    if done.returncode != 0:
        raise PdfTextError("failed")
    return done.stdout.decode("utf-8", errors=errors)
