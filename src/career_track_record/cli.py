"""Command line for track-record: ``track-record keywords ...``."""

import argparse
import os
import re
import sys

from career_track_record import barred, keywords


def _build_parser():
    parser = argparse.ArgumentParser(prog="track-record")
    top = parser.add_subparsers(dest="command", metavar="command")
    top.required = True
    kw = top.add_parser("keywords", help="scan saved job postings for terms")
    modes = kw.add_subparsers(dest="mode", metavar="mode")
    modes.required = True

    demand = modes.add_parser("demand", help="which terms the postings ask for")
    demand.add_argument("--postings", required=True, metavar="DIR")
    demand.add_argument("--terms", required=True, metavar="FILE")
    demand.add_argument("--out", metavar="FILE")

    coverage = modes.add_parser("coverage", help="which terms your copy files use")
    coverage.add_argument("--terms", required=True, metavar="FILE")
    coverage.add_argument("--keep-notes", action="store_true")
    coverage.add_argument("files", nargs="+", metavar="FILE")

    report = modes.add_parser("report", help="demand against your copy, with gaps")
    report.add_argument("--postings", required=True, metavar="DIR")
    report.add_argument("--terms", required=True, metavar="FILE")
    report.add_argument("--keep-notes", action="store_true")
    report.add_argument("--copy", required=True, nargs="+", metavar="FILE")
    # Listed for --help only: main() hands "barred" to its own parser (_parse_barred).
    top.add_parser("barred", help="report wording from your own barred list",
                   add_help=False)
    return parser


def _write(stream, text):
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        stream.flush()
        buffer.write(text.encode("utf-8", errors="backslashreplace"))
        buffer.flush()
    else:
        stream.write(text)
        stream.flush()


class _OptionError(Exception):
    """An option problem; the message is one line and never holds a value for --list."""


_BARRED_VALUE_OPTIONS = ("--list", "--control", "--min-chars")
_BARRED_OPTIONS = _BARRED_VALUE_OPTIONS + ("--strip-comments",)
_OPTION_NAME = re.compile(r"-{1,2}[A-Za-z][A-Za-z0-9-]*\Z")


def _parse_barred(args):
    """Parse the options of ``barred``. Raises _OptionError on any problem."""
    found = {"list": None, "controls": [], "strip": False, "min_chars": 500}
    seen = set()
    files = []
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            files.extend(args[i:])
            break
        if not arg.startswith("-") or arg == "-":
            files.append(arg)
            continue
        name, equals, value = arg.partition("=")
        if name == "--strip-comments":
            if equals:
                raise _OptionError("--strip-comments takes no value")
            found["strip"] = True
            continue
        if name not in _BARRED_VALUE_OPTIONS:
            raise _OptionError("unknown option")
        if not equals:
            if i >= len(args) or args[i] in _BARRED_OPTIONS:
                raise _OptionError("%s needs a value" % name)
            value = args[i]
            i += 1
        if name in ("--list", "--min-chars"):
            if name in seen:
                raise _OptionError("%s given twice" % name)
            seen.add(name)
        if name == "--list":
            found["list"] = value
        elif name == "--control":
            found["controls"].append(value)
        else:
            if not re.fullmatch(r"[0-9]+", value):
                raise _OptionError("--min-chars must be a whole number, 0 or more")
            if len(value.lstrip("0")) > 18:
                raise _OptionError("--min-chars is too large (at most 18 digits)")
            found["min_chars"] = int(value)
    found["files"] = files
    return found


def _main_barred(args, environ):
    try:
        opts = _parse_barred(args)
    except _OptionError as exc:
        _write(sys.stderr, "cannot run: %s\n" % exc)
        return 2
    list_path = opts["list"]
    if list_path is None:
        list_path = environ.get("BARRED_STRINGS_PATH") or None
    result = barred.run(list_path=list_path, files=opts["files"],
                        controls=opts["controls"], strip_comments=opts["strip"],
                        min_chars=opts["min_chars"])
    if not result.ran:
        _write(sys.stderr, result.error + "\n")
        return result.exit_code
    _write(sys.stdout, result.text)
    return result.exit_code


def main(argv=None, environ=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv and argv[0] == "barred":
        return _main_barred(argv[1:], os.environ if environ is None else environ)
    return _main_keywords(_build_parser().parse_args(argv))


def _main_keywords(args):
    try:
        terms = keywords.load_terms(args.terms)
    except keywords.KeywordError as exc:
        result = keywords.Result(2, False, error=keywords._one_line("cannot run: %s" % exc))
    else:
        if args.mode == "demand":
            result = keywords.run("demand", terms=terms, postings=args.postings)
        elif args.mode == "coverage":
            result = keywords.run("coverage", terms=terms, copy=args.files,
                                  keep_notes=args.keep_notes)
        else:
            result = keywords.run("report", terms=terms, postings=args.postings,
                                  copy=args.copy, keep_notes=args.keep_notes)
    if result.ran and args.mode == "demand" and args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(result.text[:-1])
        except OSError as exc:
            _write(sys.stderr, "cannot run: cannot write %s: %s\n"
                   % (args.out, exc.strerror or exc))
            return 2
    if not result.ran:
        _write(sys.stderr, result.error + "\n")
        return result.exit_code
    _write(sys.stdout, result.text)
    return result.exit_code
