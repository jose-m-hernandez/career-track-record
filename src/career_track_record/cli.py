"""Command line for track-record: ``track-record keywords ...``."""

import argparse
import os
import re
import sys

from career_track_record import barred, keywords, tone


class _Parser(argparse.ArgumentParser):
    """Help goes out through _out, so help that cannot be written exits 2 like any output."""

    def print_help(self, file=None):
        if file is None:
            _out(self.format_help())
        else:
            argparse.ArgumentParser.print_help(self, file)


def _build_parser():
    parser = _Parser(prog="track-record")
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
    # Listed for --help only: main() hands "tone" to its own parser (_parse_tone).
    top.add_parser("tone", help="flag hype, hedges and filler in your copy",
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


class _OutputError(Exception):
    """Standard output could not be written."""


def _silence(stream):
    """After a failed write, point the stream's descriptor at the null device, so that
    the interpreter's own final flush has nothing left to fail on."""
    try:
        fd = stream.fileno()
        null = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null, fd)
        finally:
            os.close(null)
    except Exception:
        pass


def _out(text):
    stream = sys.stdout
    if stream is None:
        raise _OutputError()
    try:
        _write(stream, text)
    except (OSError, ValueError):
        _silence(stream)
        raise _OutputError()


def _err(text):
    """Write to standard error; a closed or failing stream changes nothing."""
    stream = sys.stderr
    if stream is None:
        return
    try:
        _write(stream, text)
    except Exception:
        _silence(stream)


class _OptionError(Exception):
    """An option problem; the message is one line and never holds a value for --list."""


_BARRED_VALUE_OPTIONS = ("--list", "--control", "--min-chars")
_BARRED_OPTIONS = _BARRED_VALUE_OPTIONS + ("--strip-comments",)
_TONE_OPTIONS = ("--rules", "--warn-only", "--stale-check", "--print-defaults")

_BARRED_HELP = """\
usage: track-record barred [--list FILE] [--control TEXT]... [--strip-comments]
    [--min-chars N] FILE...

Report wording from your own barred list, by entry number only.

  --list FILE       the list file (default: $BARRED_STRINGS_PATH)
  --control TEXT    a string each file must hold (repeatable, any one counts)
  --strip-comments  strip comments and note values before matching
  --min-chars N     the minimum length of each file (default 500)
  -h, --help        show this summary and exit

exit: 0 all clean, 1 barred wording found, 2 a DEAD file or cannot run
"""

_TONE_HELP = """\
usage: track-record tone [--rules FILE] [--warn-only] [--stale-check] FILE...
       track-record tone --print-defaults

Flag hype, hedges and filler in your copy.

  --rules FILE      the rule file (default: the shipped rules)
  --warn-only       run only warn rules
  --stale-check     check exemptions for staleness
  --print-defaults  write the shipped rule file and exit
  -h, --help        show this summary and exit

exit: 0 no errors, 1 errors found, 2 it cannot run
"""


def _asks_for_help(args, value_options=(), not_values=()):
    """True when an argument before the end of the options is exactly -h or --help. It wins
    over every other argument, even one standing where an option expects its value. The
    options end at the first ``--`` that is not an option's value; value_options and
    not_values mirror the parser (a value is taken unless it is one of not_values)."""
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg in ("-h", "--help"):
            return True
        if arg == "--":
            return False
        if arg in value_options and i < len(args) and args[i] not in not_values:
            if args[i] in ("-h", "--help"):
                return True
            i += 1
    return False


def _parse_barred(args):
    """Parse the options of ``barred``. Raises _OptionError on any problem."""
    if _asks_for_help(args, _BARRED_VALUE_OPTIONS, _BARRED_OPTIONS):
        return {"help": True}
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
        _err("cannot run: %s\n" % exc)
        return 2
    if opts.get("help"):
        _out(_BARRED_HELP)
        return 0
    list_path = opts["list"]
    if list_path is None:
        list_path = environ.get("BARRED_STRINGS_PATH") or None
    result = barred.run(list_path=list_path, files=opts["files"],
                        controls=opts["controls"], strip_comments=opts["strip"],
                        min_chars=opts["min_chars"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


def _parse_tone(args):
    """Parse the options of ``tone``. Returns (options, reasons); reasons is a list of
    one-line option problems, empty when the command line is usable."""
    found = {"rules": None, "warn_only": False, "stale_check": False,
             "print_defaults": False, "files": []}
    if _asks_for_help(args):
        return {"help": True}, []
    reasons = []
    rules_given = False
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            found["files"].extend(args[i:])
            break
        if not arg.startswith("-") or arg == "-":
            found["files"].append(arg)
            continue
        name, equals, value = arg.partition("=")
        if name not in _TONE_OPTIONS:
            reasons.append("unknown option %s" % _one_line_name(name))
            continue
        if name != "--rules":
            if equals:
                reasons.append("%s takes no value" % name)
            elif name == "--warn-only":
                found["warn_only"] = True
            elif name == "--stale-check":
                found["stale_check"] = True
            else:
                found["print_defaults"] = True
            continue
        if not equals:
            if i >= len(args) or args[i].startswith("-"):
                reasons.append("--rules needs a value")
                continue
            value = args[i]
            i += 1
        if rules_given:
            reasons.append("--rules given twice")
        else:
            rules_given = True
            found["rules"] = value
    if found["print_defaults"] and args != ["--print-defaults"]:
        reasons.append("--print-defaults allows no other argument")
    return found, reasons


def _one_line_name(name):
    return name.replace("\r", "?").replace("\n", "?")


def _main_tone(args):
    opts, reasons = _parse_tone(args)
    if reasons:
        _err("".join("cannot run: %s\n" % reason for reason in reasons))
        return 2
    if opts.get("help"):
        _out(_TONE_HELP)
        return 0
    if opts["print_defaults"]:
        try:
            text = tone.default_rules_text()
        except tone.ToneError as exc:
            _err("cannot run: %s\n" % exc)
            return 2
        _out(text)
        return 0
    result = tone.run(rules_path=opts["rules"], files=opts["files"],
                      warn_only=opts["warn_only"], stale_check=opts["stale_check"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


def main(argv=None, environ=None):
    try:
        return _main(argv, environ)
    except _OutputError:
        _err("cannot run: cannot write output\n")
        return 2


def _main(argv, environ):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv and argv[0] == "barred":
        return _main_barred(argv[1:], os.environ if environ is None else environ)
    if argv and argv[0] == "tone":
        return _main_tone(argv[1:])
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
            _err("cannot run: cannot write %s: %s\n"
                   % (args.out, exc.strerror or exc))
            return 2
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code
