"""Command line for track-record: ``track-record keywords ...``."""

import argparse
import os
import re
import sys

from career_track_record import (ab, barred, claims, config, drafts, keywords, panel,
                                 parse, reader_harness, record_check, setup_cmd, tone,
                                 write_guard, wrapped_compounds)


class _MissingRequired(Exception):
    """A required argument was absent; ``parser.error`` was asked to say so."""

    def __init__(self, parser, message):
        Exception.__init__(self, message)
        self.parser = parser
        self.message = message


_CATCH_REQUIRED = [False]


class _Parser(argparse.ArgumentParser):
    """Help goes out through _out, so help that cannot be written exits 2 like any output."""

    def print_help(self, file=None):
        if file is None:
            _out(self.format_help())
        else:
            argparse.ArgumentParser.print_help(self, file)

    def error(self, message):
        """A usage error goes out through _err, as argparse's own would, and exits 2 even
        when standard error is closed or cannot be written. While keywords arguments are
        being parsed for config defaults, a missing required argument is raised instead, so
        the caller may fill it from the config and say the same words if it cannot."""
        if _CATCH_REQUIRED[0] and message.startswith("the following arguments are required: "):
            raise _MissingRequired(self, message)
        self.say(message)

    def say(self, message):
        _err(self.format_usage())
        _err("%s: error: %s\n" % (self.prog, message))
        raise SystemExit(2)


def _build_parser():
    parser = _Parser(prog="track-record")
    top = parser.add_subparsers(dest="command", metavar="command")
    top.required = True
    kw = top.add_parser("keywords", help="scan saved job postings for terms")
    modes = kw.add_subparsers(dest="mode", metavar="mode")
    modes.required = True

    demand = modes.add_parser("demand", help="which terms the postings ask for")
    demand.add_argument("--postings", required=True, metavar="DIR")
    demand.add_argument("--terms", required=True, metavar="FILE",
                        help=keywords.TERMS_HELP)
    demand.add_argument("--out", metavar="FILE")

    coverage = modes.add_parser("coverage", help="which terms your copy files use")
    coverage.add_argument("--terms", required=True, metavar="FILE",
                          help=keywords.TERMS_HELP)
    coverage.add_argument("--keep-notes", action="store_true")
    coverage.add_argument("files", nargs="+", metavar="FILE")

    report = modes.add_parser("report", help="demand against your copy, with gaps")
    report.add_argument("--postings", required=True, metavar="DIR")
    report.add_argument("--terms", required=True, metavar="FILE",
                        help=keywords.TERMS_HELP)
    report.add_argument("--keep-notes", action="store_true")
    report.add_argument("--copy", required=True, nargs="+", metavar="FILE")
    # Listed for --help only: main() hands "barred" to its own parser (_parse_barred).
    top.add_parser("barred", help="report wording from your own barred list",
                   add_help=False)
    # Listed for --help only: main() hands "tone" to its own parser (_parse_tone).
    top.add_parser("tone", help="flag hype, hedges and filler in your copy",
                   add_help=False)
    # Listed for --help only: main() hands "ab" to its own parser (_parse_plan_command).
    top.add_parser("ab", help="compare two versions of your copy with test readers",
                   add_help=False)
    # Listed for --help only: main() hands "claims" to its own parser (_parse_claims).
    top.add_parser("claims", help="fail on sentences your claims list hasn't approved",
                   add_help=False)
    # Listed for --help only: main() hands "panel" to its own parser (_parse_plan_command).
    top.add_parser("panel", help="read one version blind through named lenses",
                   add_help=False)
    # Listed for --help only: main() hands "record" to its own parser (_parse_record).
    top.add_parser("record", help="check your record's tables against rules you declare",
                   add_help=False)
    # Listed for --help only: main() hands "drafts" to its own parser (_parse_drafts).
    top.add_parser("drafts", help="check a file of a document's versions, or extract one",
                   add_help=False)
    # Listed for --help only: main() hands "wrapped-compounds" to its own parser
    # (_parse_wrapped).
    top.add_parser("wrapped-compounds",
                   help="find hyphenated words split across two lines in a PDF",
                   add_help=False)
    # Listed for --help only: main() hands "parse" to its own parser (_parse_options).
    top.add_parser("parse", help="check what a text extractor gets from your r\u00e9sum\u00e9 PDF",
                   add_help=False)
    # Listed for --help only: main() hands "setup" to its own parser (_parse_setup).
    top.add_parser("setup", help="choose your record folder", add_help=False)
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


def _config_paths(environ, names):
    """The config's default path for each of ``names`` (file or folder names under the
    record folder), each announced by one ``using`` line on standard error. Returns
    ({name: path}, False): empty when there is no config file. A config that is not usable,
    or a record folder that is missing, writes the "track-record config is not usable" line (naming the reason, not the
    folder) and returns (None, True)."""
    try:
        defaults = config.load_defaults(environ)
    except config.ConfigError as exc:
        _err(exc.line() + "\n")
        return None, True
    if defaults is None:
        return {}, False
    found = {}
    for name in names:
        found[name] = defaults.path(name)
        _err(defaults.using(name) + "\n")
    return found, False


def _write_refused(targets, environ):
    """None when a write to ``targets`` (complete output paths) may go ahead. Otherwise the
    refusal's one line is on standard error and the result is the exit code to end with."""
    try:
        write_guard.recheck(targets, environ)
    except write_guard.Refusal as refusal:
        _err(refusal.line + "\n")
        return refusal.code
    return None


_BARRED_VALUE_OPTIONS = ("--list", "--control", "--min-chars")
_BARRED_OPTIONS = _BARRED_VALUE_OPTIONS + ("--strip-comments",)
_CLAIMS_VALUE_OPTIONS = ("--list", "--control")
_CLAIMS_OPTIONS = _CLAIMS_VALUE_OPTIONS + ("--stale-check", "--check-sources")
_TONE_OPTIONS = ("--rules", "--warn-only", "--stale-check", "--print-defaults")
_TONE_RULES = "tone-rules.json"

_BARRED_HELP = """\
usage: track-record barred [--list FILE] [--control TEXT]... [--strip-comments]
    [--min-chars N] FILE...

Report wording from your own barred list, by entry number only.

  --list FILE       the list file (default: $BARRED_STRINGS_PATH, else your record folder)
  --control TEXT    a string each file must hold (repeatable, any one counts)
  --strip-comments  strip comments and note values before matching
  --min-chars N     the minimum length of each file (default 500)
  -h, --help        show this summary and exit

exit: 0 all clean, 1 barred wording found, 2 a DEAD file or cannot run
"""

_WRAPPED_HELP = """\
usage: track-record wrapped-compounds --control TEXT [--control TEXT]... FILE...

Checks a PDF for hyphenated words (such as well-known) that are split across
two lines. Some programs that read a PDF's text join the two halves into one
word ("wellknown"), so a text search misses it even though the page looks right.

Run it on the final PDF, after your last edit. Exit 0 means no split hyphenated
word needs a fix. It checks nothing else about the file.

  --control TEXT  text that must appear in the file, such as your name;
                  repeatable; if none appears the file is reported DEAD
                  (it could not be checked), never OK
  -h, --help      show this summary and exit

exit: 0 no finding, 1 a finding, 2 no verdict (a file is DEAD, or the command
      could not run); 2 is not a pass
"""

_PARSE_HELP = """\
usage: track-record parse --name TEXT [--contact TEXT]... [--sections LIST]
                          [--min-page-chars N] FILE...

Shows what a program that reads a PDF's text gets from your résumé: whether
there is text on every page, whether your name and contact details are on
page 1, which common English section headings (such as Experience or Skills)
it can see, how many date formats your date ranges use, and whether a
hyphenated word is split across two lines.

It cannot tell what any particular hiring system will accept. A file can
pass here and still be misread by one.

  --name TEXT          your name as it appears in the PDF (required); if it is
                       not found the file is reported DEAD (it could not be
                       checked)
  --contact TEXT       an email, phone number or link, written as it appears
                       in the PDF, that should be on page 1; repeatable
  --sections LIST      section families that must appear, separated by commas
                       (default: experience,skills); families: experience,
                       education, skills, summary, projects, certifications
  --min-page-chars N   a page with fewer letters or digits than this is
                       reported as having little or no text (default 20)
  -h, --help           show this summary and exit

exit: 0 no finding, 1 a finding, 2 no verdict (a file is DEAD, or the command
      could not run); 2 is not a pass
"""

_TONE_HELP = """\
usage: track-record tone [--rules FILE] [--warn-only] [--stale-check] FILE...
       track-record tone --print-defaults

Flag hype, hedges and filler in your copy.

  --rules FILE      the rule file (default: your record folder, else the shipped rules)
  --warn-only       run only warn rules
  --stale-check     check exemptions for staleness
  --print-defaults  write the shipped rule file and exit
  -h, --help        show this summary and exit

exit: 0 no errors, 1 errors found, 2 it cannot run
"""


_CLAIMS_HELP = """\
usage: track-record claims --list FILE --control TEXT [--control TEXT]...
    [--stale-check] [--check-sources] FILE...

Fail on any sentence your claims list has not approved.

  --list FILE      the claims list (required unless claims-list.txt is in your record folder)
  --control TEXT   a string each file must hold (repeatable, any one counts)
  --stale-check    also report approved entries no file uses
  --check-sources  also check each quote against the source file it cites
  -h, --help       show this summary and exit

exit: 0 every sentence approved, 1 a sentence not approved, 2 a DEAD file or cannot run;
    with --check-sources, also 1 a quote not found, 2 a source that cannot be read
"""


_RECORD_HELP = """\
usage: track-record record [--report-only] DECLARATION

Check the tables of your record against the rules you declare.

  --report-only  report findings but exit 0 for them
  -h, --help     show this summary and exit

exit: 0 all checks OK, 1 a check found a problem, 2 a DEAD check or cannot run
"""


_DRAFTS_HELP = """\
usage: track-record drafts check FILE [--earlier COPY]
       track-record drafts extract FILE ID --out OUT [--earlier COPY]

Check the file that holds a document's versions, or write out one version.

  --earlier COPY  an earlier copy that must still be the start of FILE
  --out OUT       the new file extract writes; it must not exist
  -h, --help      show this summary and exit

exit: 0 OK, 1 a fault that check reports or extract refuses,
      2 a DEAD check or cannot run
"""


_SETUP_HELP = """\
usage: track-record setup [--folder PATH]
       track-record setup --show

Choose your record folder: ask once, write a small config naming it, and make the
folder and its four layout folders. It runs no check.

  --folder PATH  use PATH as the record folder and ask nothing
  --show         show the config and the folder each command would use
  -h, --help     show this summary and exit

config: $CTR_CONFIG_DIR/config.json, else $XDG_CONFIG_HOME/track-record/config.json,
    else ~/.config/track-record/config.json

exit: 0 done, kept or shown, 1 the folder is refused (git tracks it, or a work tree does
    not ignore it), 2 it cannot run
"""


_AB_SUBCOMMANDS = ("freeze", "run", "score")

_AB_HELP = """\
usage: track-record ab freeze PLAN
       track-record ab run PLAN [--live]
       track-record ab score PLAN

Compare two versions of your copy with test readers, under a plan you freeze first.

  freeze PLAN        check the plan and hash it with every file it names
  run PLAN [--live]  check the hashes, run the readers and write a result
  score PLAN         score the replies again and write a new result
  -h, --help         show this summary and exit

Each subcommand also takes -h.

exit: 0 it completed, 1 a read failed or the run was cut, 2 it cannot run
"""

_AB_FREEZE_HELP = """\
usage: track-record ab freeze PLAN

Read the plan, check every file it names, and write the freeze file beside it. Every
plan problem is found here, and no reader runs.

  -h, --help  show this summary and exit

exit: 0 the freeze was written, 2 it cannot run
"""

_AB_RUN_HELP = """\
usage: track-record ab run PLAN [--live]

Check the freeze and the versions, run the readers and score their replies. A plan with a
live reader (a command you name) only prints that command and the spend estimate, and
starts nothing, until you add --live.

  --live      start the live readers
  -h, --help  show this summary and exit

exit: 0 it completed, 1 a read failed or the run was cut, 2 it cannot run
"""

_AB_SCORE_HELP = """\
usage: track-record ab score PLAN

Check the freeze and score the replies in the run folder again, into a new result file.

  -h, --help  show this summary and exit

exit: 0 it completed, 1 a read failed or the run was cut, 2 it cannot run
"""

_AB_HELPS = {"ab": _AB_HELP, "freeze": _AB_FREEZE_HELP, "run": _AB_RUN_HELP,
             "score": _AB_SCORE_HELP}

_PANEL_HELP = """\
usage: track-record panel freeze PLAN
       track-record panel run PLAN [--live]
       track-record panel score PLAN

Read one version of your copy blind through named lenses, each gated by two planted
anchors, under a plan you freeze first.

  freeze PLAN        check the plan and hash it with every file it names
  run PLAN [--live]  check the hashes, run the readers and write a result
  score PLAN         score the replies again and write a new result
  -h, --help         show this summary and exit

Each subcommand also takes -h.

exit: 0 it completed, 1 a read failed or the run was cut, 2 it cannot run
"""

_PANEL_FREEZE_HELP = """\
usage: track-record panel freeze PLAN

Read the plan, check every file it names, and write the freeze file beside it. Every
plan problem is found here, and no reader runs.

  -h, --help  show this summary and exit

exit: 0 the freeze was written, 2 it cannot run
"""

_PANEL_RUN_HELP = """\
usage: track-record panel run PLAN [--live]

Check the freeze and the documents, run the readers and score their replies. A plan with
a live reader (a command you name) only prints that command and the spend estimate, and
starts nothing, until you add --live.

  --live      start the live readers
  -h, --help  show this summary and exit

exit: 0 it completed, 1 a read failed or the run was cut, 2 it cannot run
"""

_PANEL_SCORE_HELP = """\
usage: track-record panel score PLAN

Check the freeze and score the replies in the run folder again, into a new result file.

  -h, --help  show this summary and exit

exit: 0 it completed, 1 a read failed or the run was cut, 2 it cannot run
"""

_PANEL_HELPS = {"panel": _PANEL_HELP, "freeze": _PANEL_FREEZE_HELP, "run": _PANEL_RUN_HELP,
                "score": _PANEL_SCORE_HELP}

# The two plan commands share a command line: <command> <subcommand> PLAN [--live].
_PLAN_COMMANDS = {"ab": (ab, _AB_HELPS), "panel": (panel, _PANEL_HELPS)}


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


def _parse_setup(args):
    """Parse the options of ``setup``. Raises _OptionError on any problem."""
    if _asks_for_help(args, ("--folder",), ("--folder", "--show")):
        return {"help": True}
    folder = None
    show = False
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--" or not arg.startswith("-") or arg == "-":
            extra = args[i:] if arg == "--" else [arg]
            if arg == "--" and not extra:
                break
            raise _OptionError("setup: extra argument %s" % barred.printed_path(extra[0]))
        name, equals, value = arg.partition("=")
        if name == "--show":
            if equals:
                raise _OptionError("setup: --show takes no value")
            if show:
                raise _OptionError("setup: --show given twice")
            show = True
            continue
        if name != "--folder":
            raise _OptionError("setup: unknown option %s" % barred.printed_path(name))
        if folder is not None:
            raise _OptionError("setup: --folder given twice")
        if not equals:
            if i >= len(args) or args[i].startswith("-") or args[i] == "":
                raise _OptionError("setup: --folder needs a value")
            value = args[i]
            i += 1
        elif value == "":
            raise _OptionError("setup: --folder needs a value")
        folder = value
    if show and folder is not None:
        raise _OptionError("setup: --show allows no other option")
    return {"folder": folder, "show": show}


def _main_setup(args, environ):
    try:
        opts = _parse_setup(args)
    except _OptionError as exc:
        _err("cannot run: %s\n" % exc)
        return 2
    if opts.get("help"):
        _out(_SETUP_HELP)
        return 0
    try:
        if opts["show"]:
            return setup_cmd.show(_out, _err, environ)
        return setup_cmd.run(opts["folder"], _out, _err, environ)
    except KeyboardInterrupt:
        _err("cannot run: setup: interrupted\n")
        return 2


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
            significant = value.lstrip("0")
            if len(significant) > 18:
                raise _OptionError("--min-chars is too large (at most 18 digits)")
            found["min_chars"] = int(significant or "0")
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
    if list_path is None:
        found, failed = _config_paths(environ, ("barred-list.txt",))
        if failed:
            return 2
        list_path = found.get("barred-list.txt")
    result = barred.run(list_path=list_path, files=opts["files"],
                        controls=opts["controls"], strip_comments=opts["strip"],
                        min_chars=opts["min_chars"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


def _parse_wrapped(args):
    """Parse the options of ``wrapped-compounds`` as ``barred``'s are parsed. Raises
    _OptionError on any problem; an unknown option outranks a missing value."""
    if _asks_for_help(args, ("--control",), ("--control",)):
        return {"help": True}
    controls = []
    files = []
    missing = None
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
        if name != "--control":
            raise _OptionError("unknown option")
        if not equals:
            if i >= len(args) or args[i] == "--control":
                missing = missing or _OptionError("--control needs a value")
                continue
            value = args[i]
            i += 1
        controls.append(value)
    if missing is not None:
        raise missing
    return {"controls": controls, "files": files}


def _main_wrapped(args):
    """No configuration is read: the only inputs are the arguments and the files."""
    try:
        opts = _parse_wrapped(args)
    except _OptionError as exc:
        _err("cannot run: %s\n" % exc)
        return 2
    if opts.get("help"):
        _out(_WRAPPED_HELP)
        return 0
    result = wrapped_compounds.run(files=opts["files"], controls=opts["controls"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


_PARSE_VALUE_OPTIONS = ("--name", "--contact", "--sections", "--min-page-chars")


def _parse_options(args):
    """Parse the options of ``parse`` (usage errors 1 to 3 of its spec, left to right). The
    checks of the values are the run's. Raises _OptionError on any problem."""
    if _asks_for_help(args, _PARSE_VALUE_OPTIONS, _PARSE_VALUE_OPTIONS):
        return {"help": True}
    found = {"name": None, "contacts": [], "sections": None, "min_page_chars": None,
             "files": []}
    seen = set()
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
        if name not in _PARSE_VALUE_OPTIONS:
            raise _OptionError("unknown option %s" % barred.printed_path(arg))
        if not equals:
            if i >= len(args) or args[i] in _PARSE_VALUE_OPTIONS:
                raise _OptionError("%s needs a value" % name)
            value = args[i]
            i += 1
        if name == "--contact":
            found["contacts"].append(value)
            continue
        if name in seen:
            raise _OptionError("%s given twice" % name)
        seen.add(name)
        found[name[2:].replace("-", "_")] = value
    return found


def _main_parse(args):
    """No configuration is read: the only inputs are the arguments and the files."""
    try:
        opts = _parse_options(args)
    except _OptionError as exc:
        _err("cannot run: %s\n" % exc)
        return 2
    if opts.get("help"):
        _out(_PARSE_HELP)
        return 0
    result = parse.run(files=opts["files"], name=opts["name"], contacts=opts["contacts"],
                       sections=opts["sections"], min_page_chars=opts["min_page_chars"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


def _parse_claims(args):
    """Parse the options of ``claims``. Raises _OptionError on any problem."""
    if _asks_for_help(args, _CLAIMS_VALUE_OPTIONS, _CLAIMS_OPTIONS):
        return {"help": True}
    found = {"list": None, "controls": [], "stale_check": False, "check_sources": False,
             "files": []}
    list_given = False
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
        if name == "--stale-check" and not equals:
            found["stale_check"] = True
            continue
        if name == "--check-sources" and not equals:
            found["check_sources"] = True
            continue
        if name not in _CLAIMS_VALUE_OPTIONS:
            raise _OptionError("unknown option %s" % barred.printed_path(arg))
        if not equals:
            if i >= len(args) or args[i] in _CLAIMS_OPTIONS:
                raise _OptionError("%s needs a value" % name)
            value = args[i]
            i += 1
        if name == "--list":
            if list_given:
                raise _OptionError("--list given twice")
            list_given = True
            found["list"] = value
        else:
            found["controls"].append(value)
    return found


def _main_claims(args, environ):
    try:
        opts = _parse_claims(args)
    except _OptionError as exc:
        _err("cannot run: %s\n" % exc)
        return 2
    if opts.get("help"):
        _out(_CLAIMS_HELP)
        return 0
    list_path = opts["list"]
    if list_path is None:
        found, failed = _config_paths(environ, ("claims-list.txt",))
        if failed:
            return 2
        list_path = found.get("claims-list.txt")
    result = claims.run(list_path=list_path, files=opts["files"],
                        controls=opts["controls"], stale_check=opts["stale_check"],
                        check_sources=opts["check_sources"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


def _parse_record(args):
    """Parse the command line of ``record``. Raises _OptionError on any problem."""
    if _asks_for_help(args):
        return {"help": True}
    report_only = False
    declarations = []
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            declarations.extend(args[i:])
            break
        if not arg.startswith("-") or arg == "-":
            declarations.append(arg)
            continue
        name, equals, _value = arg.partition("=")
        if name != "--report-only":
            raise _OptionError("unknown option %s" % barred.printed_path(name))
        if equals:
            raise _OptionError("--report-only takes no value")
        report_only = True
    if not declarations:
        raise _OptionError("record needs a DECLARATION file")
    if len(declarations) > 1:
        raise _OptionError("record takes one DECLARATION file, not several")
    return {"declaration": declarations[0], "report_only": report_only}


def _main_record(args):
    try:
        opts = _parse_record(args)
    except _OptionError as exc:
        _err("cannot run: %s\n" % exc)
        return 2
    if opts.get("help"):
        _out(_RECORD_HELP)
        return 0
    result = record_check.run(opts["declaration"], report_only=opts["report_only"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


_DRAFTS_VALUE_OPTIONS = {"check": ("--earlier",), "extract": ("--earlier", "--out")}


def _parse_drafts(args):
    """Parse the command line of ``drafts``. Raises _OptionError on any problem, naming the
    first one in the order the checks run: the subcommand, then the options left to right,
    then the FILE and the arguments after it."""
    if _asks_for_help(args, ("--earlier", "--out"), ("--earlier", "--out")):
        return {"help": True}
    if not args:
        raise _OptionError("drafts needs check or extract")
    sub = args[0]
    if sub not in _DRAFTS_VALUE_OPTIONS:
        raise _OptionError("unknown subcommand %s" % barred.printed_path(sub))
    allowed = _DRAFTS_VALUE_OPTIONS[sub]
    given = {}
    words = []
    i = 1
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            words.extend(args[i:])
            break
        if not arg.startswith("-") or arg == "-":
            words.append(arg)
            continue
        name, equals, value = arg.partition("=")
        if name not in allowed:
            raise _OptionError("unknown option %s" % barred.printed_path(name))
        if name in given:
            raise _OptionError("%s given more than once" % name)
        if not equals:
            if i >= len(args) or args[i] in ("--earlier", "--out"):
                raise _OptionError("%s needs a value" % name)
            value = args[i]
            i += 1
        elif value == "":
            raise _OptionError("%s needs a value" % name)
        given[name] = value
    if not words:
        raise _OptionError("%s needs a FILE" % sub)
    if len(words) > (1 if sub == "check" else 2):
        raise _OptionError("%s takes one FILE, not several" % sub)
    if sub == "extract":
        if len(words) < 2:
            raise _OptionError("extract needs a version id")
        if "--out" not in given:
            raise _OptionError("extract needs --out OUT")
    return {"sub": sub, "file": words[0], "id": words[1] if len(words) > 1 else None,
            "earlier": given.get("--earlier"), "out": given.get("--out")}


def _err_strict(text):
    """Write to standard error; a closed or failing stream raises OSError."""
    stream = sys.stderr
    if stream is None:
        raise OSError("no standard error")
    try:
        _write(stream, text)
    except (OSError, ValueError):
        _silence(stream)
        raise OSError("standard error cannot be written")


def _main_drafts(args, environ):
    try:
        opts = _parse_drafts(args)
    except _OptionError as exc:
        _err("cannot run: %s\n" % exc)
        return 2
    if opts.get("help"):
        _out(_DRAFTS_HELP)
        return 0
    if opts["sub"] == "check":
        result = drafts.check(opts["file"], opts["earlier"])
    else:
        refused = _write_refused([opts["out"]], environ)
        if refused is not None:
            return refused
        result = drafts.extract(opts["file"], opts["id"], opts["out"], opts["earlier"],
                                emit=_err_strict)
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    if opts["sub"] == "check":
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


def _main_tone(args, environ):
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
    rules_path = opts["rules"]
    if rules_path is None:
        try:
            defaults = config.load_defaults(environ)
        except config.ConfigError as exc:
            _err(exc.line() + "\n")
            return 2
        if defaults is not None:
            if os.path.lexists(defaults.path(_TONE_RULES)):
                _err(defaults.using(_TONE_RULES) + "\n")
                rules_path = defaults.path(_TONE_RULES)
            else:
                _err("no %s in %s; using the shipped rules\n"
                     % (_TONE_RULES, barred.printed_path(defaults.folder)))
    result = tone.run(rules_path=rules_path, files=opts["files"],
                      warn_only=opts["warn_only"], stale_check=opts["stale_check"])
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code


def _parse_plan_command(command, args):
    """Parse the command line of ``ab`` or ``panel`` (``command``). Returns a dict, or raises
    _OptionError with the first problem."""
    sub = args[0] if args and args[0] in _AB_SUBCOMMANDS else None
    if _asks_for_help(args[1:] if sub else args):
        return {"help": sub or command}
    if not args:
        raise _OptionError("%s needs a subcommand: freeze, run or score" % command)
    if sub is None:
        if args[0].startswith("-") and args[0] != "-":
            raise _OptionError("unknown option %s"
                               % barred.printed_path(args[0].partition("=")[0]))
        raise _OptionError("unknown %s subcommand %s" % (command, barred.printed_path(args[0])))
    live = False
    plans = []
    rest = args[1:]
    i = 0
    while i < len(rest):
        arg = rest[i]
        i += 1
        if arg == "--":
            plans.extend(rest[i:])
            break
        if not arg.startswith("-") or arg == "-":
            plans.append(arg)
            continue
        name, equals, _value = arg.partition("=")
        if sub != "run" or name != "--live":
            raise _OptionError("unknown option %s" % barred.printed_path(name))
        if equals:
            raise _OptionError("--live takes no value")
        live = True
    if not plans:
        raise _OptionError("%s %s needs a PLAN file" % (command, sub))
    if len(plans) > 1:
        raise _OptionError("%s %s takes one PLAN file, not several" % (command, sub))
    return {"sub": sub, "plan": plans[0], "live": live}


def _main_plan_command(command, args, environ):
    """Run ``ab`` or ``panel``: the two share a command line and an exit discipline."""
    module, helps = _PLAN_COMMANDS[command]
    try:
        opts = _parse_plan_command(command, args)
    except _OptionError as exc:
        _err("cannot run: %s\n" % exc)
        return 2
    if "help" in opts:
        _out(helps[opts["help"]])
        return 0
    refused = _write_refused(write_guard.plan_targets(opts["sub"], opts["plan"]), environ)
    if refused is not None:
        return refused
    # ab checks its series file against the record folder with the same environment; panel
    # has no series file and takes none
    extra = {"environ": environ} if command == "ab" else {}
    try:
        if opts["sub"] == "freeze":
            result = module.freeze(opts["plan"], **extra)
        elif opts["sub"] == "run":
            result = module.run(opts["plan"], live=opts["live"], **extra)
        else:
            result = module.score(opts["plan"], **extra)
    except KeyboardInterrupt:
        # An interrupt ends any ab or panel command with exit 2 and one line, never a
        # traceback. run has already put "stopped: interrupted" at the end of its run log.
        _err("cannot run: stopped: interrupted\n")
        return 2
    if result.refusal is not None:
        _err(result.refusal + "\n")
        return result.exit_code
    if not result.ran:
        _err("".join("cannot run: %s\n" % line for line in result.error.split("\n")))
        return result.exit_code
    _out(result.text)
    if result.warnings:
        _err(result.warnings)
    if result.stopped is not None:
        _err("cannot run: stopped: %s\n" % result.stopped)
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
        return _main_tone(argv[1:], os.environ if environ is None else environ)
    if argv and argv[0] in _PLAN_COMMANDS:
        return _main_plan_command(argv[0], argv[1:], os.environ if environ is None else environ)
    if argv and argv[0] == "claims":
        return _main_claims(argv[1:], os.environ if environ is None else environ)
    if argv and argv[0] == "record":
        return _main_record(argv[1:])
    if argv and argv[0] == "drafts":
        return _main_drafts(argv[1:], os.environ if environ is None else environ)
    if argv and argv[0] == "wrapped-compounds":
        return _main_wrapped(argv[1:])
    if argv and argv[0] == "parse":
        return _main_parse(argv[1:])
    if argv and argv[0] == "setup":
        return _main_setup(argv[1:], os.environ if environ is None else environ)
    return _main_keywords(argv, os.environ if environ is None else environ)


_KEYWORDS_DEFAULTS = (("--postings", "postings"), ("--terms", "terms.tsv"))


def _keywords_args(argv, environ):
    """The parsed keywords command line, with ``--postings`` and ``--terms`` taken from the
    config when the command line lacks them. Returns (args, error code or None). When the
    config cannot supply what is missing, the usage error is argparse's own words, as before
    the config existed; the config is read only when one of those two flags is missing and
    nothing else required is."""
    _CATCH_REQUIRED[0] = True
    try:
        try:
            return _build_parser().parse_args(argv), None
        except _MissingRequired as missing:
            first = missing
    finally:
        _CATCH_REQUIRED[0] = False
    names = first.message.split(": ", 1)[1].split(", ")
    flags = dict(_KEYWORDS_DEFAULTS)
    if any(name not in flags for name in names):
        first.parser.say(first.message)
    try:
        defaults = config.load_defaults(environ)
    except config.ConfigError as exc:
        _err(exc.line() + "\n")
        return None, 2
    if defaults is None:
        first.parser.say(first.message)
    injected = []
    for flag, name in _KEYWORDS_DEFAULTS:
        if flag in names:
            injected += [flag, defaults.path(name)]
    args = _build_parser().parse_args(argv[:2] + injected + argv[2:])
    for flag, name in _KEYWORDS_DEFAULTS:
        if flag in names:
            _err(defaults.using(name) + "\n")
    return args, None


def _target_is_new(path):
    """True when nothing is at ``path`` (a link, even a dangling one, is something)."""
    try:
        return not os.path.lexists(path)
    except (OSError, ValueError):
        return False


def _write_demand(out, text, was_new):
    """Write the demand table to ``out``. A file that was not there when ``was_new`` was
    decided is created exclusively and without following a link at its path, so a link put
    there afterwards makes the open fail; a file that existed is opened to be replaced, as it
    always was."""
    if was_new:
        handle = reader_harness.open_new(out, False, encoding="utf-8", newline="\n")
    else:
        handle = open(out, "w", encoding="utf-8", newline="\n")
    with handle:
        handle.write(text)


def _main_keywords(argv, environ):
    args, failed = _keywords_args(argv, environ)
    if failed:
        return failed
    out_was_new = False
    if args.mode == "demand" and args.out:
        out_was_new = _target_is_new(args.out)
        refused = _write_refused([args.out], environ)
        if refused is not None:
            return refused
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
            _write_demand(args.out, result.text[:-1], out_was_new)
        except OSError as exc:
            _err("cannot run: cannot write %s: %s\n"
                 % (barred.printed_path(args.out), exc.strerror or exc))
            return 2
    if not result.ran:
        _err(result.error + "\n")
        return result.exit_code
    _out(result.text)
    return result.exit_code
