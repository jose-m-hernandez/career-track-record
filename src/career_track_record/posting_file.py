"""Read and write the saved-posting file format.

A posting is a headed file (six header lines, an optional control line, the
body) or a raw file with a ``<name>.txt.meta.json`` sidecar. Every problem
with a posting raises ``PostingError``.
"""

import hashlib
import json
import os

HEADER_KEYS = ("source_url", "api_endpoint", "fetched_at", "http_status", "sha256", "bytes")
SIDECAR_FORMAT = "raw-posting-with-sidecar"

# Cases of the keyword-scan spec, section 8.
CASE_MALFORMED_HEADER = 2
CASE_MISMATCH = 3
CASE_NOT_UTF8 = 8


class PostingError(Exception):
    """A posting cannot be read. ``case`` is the spec's section 8 case."""

    def __init__(self, case, message):
        Exception.__init__(self, message)
        self.case = case
        self.message = message


class Posting(object):
    """A posting read from disk.

    ``body`` is the searched text, ``fields`` holds the header values (or the
    sidecar's), ``control`` is the control line or None, ``sidecar`` is True
    for a raw posting.
    """

    def __init__(self, path, body, fields, control=None, sidecar=False):
        self.path = path
        self.body = body
        self.fields = fields
        self.control = control
        self.sidecar = sidecar


def sha256_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _translate_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read_text(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise PostingError(CASE_NOT_UTF8, "%s is not valid UTF-8" % os.path.basename(path))
    return _translate_newlines(text)


def _is_control_line(line):
    return line.startswith("control") and ": " in line


def read_posting(path):
    """Read one posting file; use its sidecar when one sits beside it."""
    name = os.path.basename(path)
    sidecar_path = path + ".meta.json"
    if os.path.isfile(sidecar_path):
        return _read_raw(path, sidecar_path, name)
    return _read_headed(path, name)


def _read_headed(path, name):
    text = _read_text(path)
    parts = text.split("\n")
    count = len(parts) - (1 if parts[-1] == "" else 0)
    if count < 7:
        raise PostingError(
            CASE_MALFORMED_HEADER,
            "%s: header is malformed: fewer than seven lines" % name,
        )
    fields = {}
    for index, key in enumerate(HEADER_KEYS):
        line = parts[index]
        found, separator, value = line.partition(": ")
        if not separator:
            raise PostingError(
                CASE_MALFORMED_HEADER,
                "%s: header is malformed: line %d lacks the '%s: ' separator"
                % (name, index + 1, key),
            )
        if found != key:
            raise PostingError(
                CASE_MALFORMED_HEADER,
                "%s: header is malformed: line %d should be '%s', not '%s'"
                % (name, index + 1, key, found),
            )
        if value == "":
            raise PostingError(
                CASE_MALFORMED_HEADER,
                "%s: header is malformed: '%s' has an empty value" % (name, key),
            )
        fields[key] = value
    start = 6
    control = None
    if _is_control_line(parts[6]):
        control = parts[6]
        start = 7
        if start < len(parts) and parts[start].strip() == "":
            start = 8
    body = "\n".join(parts[start:])
    if not body.strip():
        raise PostingError(CASE_MISMATCH, "%s: body is blank" % name)
    if sha256_of(body) != fields["sha256"]:
        raise PostingError(
            CASE_MISMATCH, "%s: body does not match its recorded sha256" % name
        )
    return Posting(path, body, fields, control=control)


def _read_raw(path, sidecar_path, name):
    try:
        with open(sidecar_path, "rb") as handle:
            raw = handle.read()
        meta = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise PostingError(CASE_NOT_UTF8, "%s.meta.json is not valid UTF-8" % name)
    except ValueError:
        raise PostingError(CASE_MISMATCH, "%s.meta.json is not valid JSON" % name)
    if not isinstance(meta, dict):
        raise PostingError(CASE_MISMATCH, "%s.meta.json is not a JSON object" % name)
    if meta.get("format") != SIDECAR_FORMAT:
        raise PostingError(
            CASE_MISMATCH,
            "%s.meta.json: format is not '%s'" % (name, SIDECAR_FORMAT),
        )
    source_url = meta.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise PostingError(
            CASE_MISMATCH, "%s.meta.json: source_url is not an https:// string" % name
        )
    size = meta.get("bytes")
    if not isinstance(size, int) or isinstance(size, bool):
        raise PostingError(CASE_MISMATCH, "%s.meta.json: bytes is not an integer" % name)
    digest = meta.get("sha256")
    if not isinstance(digest, str):
        raise PostingError(CASE_MISMATCH, "%s.meta.json: sha256 is not a string" % name)
    with open(path, "rb") as handle:
        stored = handle.read()
    if len(stored) != size:
        raise PostingError(
            CASE_MISMATCH, "%s: does not match the bytes in its sidecar" % name
        )
    if hashlib.sha256(stored).hexdigest() != digest:
        raise PostingError(
            CASE_MISMATCH, "%s: does not match the sha256 in its sidecar" % name
        )
    try:
        text = stored.decode("utf-8")
    except UnicodeDecodeError:
        raise PostingError(CASE_NOT_UTF8, "%s is not valid UTF-8" % name)
    body = _translate_newlines(text)
    if not body.strip():
        raise PostingError(CASE_MISMATCH, "%s: body is blank" % name)
    fields = {"source_url": source_url, "bytes": str(size), "sha256": digest}
    return Posting(path, body, fields, sidecar=True)


def write_posting(path, *, source_url, api_endpoint, fetched_at, http_status,
                  body, control=None):
    """Write a headed posting file.

    ``sha256`` and ``bytes`` come from the body (bytes = its UTF-8 length).
    ``control`` is the value of an optional control line, written as
    ``control: <value>`` and followed by one blank line. The file uses ``\\n``
    line endings and has no line feed after the body.
    """
    body = _translate_newlines(body)
    values = [source_url, api_endpoint, fetched_at, str(http_status)]
    for key, value in zip(HEADER_KEYS, values):
        if value == "" or "\n" in value or "\r" in value:
            raise ValueError("%s must be a non-empty single line" % key)
    if control is None and _is_control_line(body.split("\n", 1)[0]):
        raise ValueError("the body's first line would be read as a control line")
    if control is not None and ("\n" in control or "\r" in control):
        raise ValueError("control must be a single line")
    lines = [
        "source_url: " + source_url,
        "api_endpoint: " + api_endpoint,
        "fetched_at: " + fetched_at,
        "http_status: " + str(http_status),
        "sha256: " + sha256_of(body),
        "bytes: " + str(len(body.encode("utf-8"))),
    ]
    if control is not None:
        lines.append("control: " + control)
        lines.append("")
    text = "\n".join(lines) + "\n" + body
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
