"""Command line for track-record: ``track-record keywords ...``."""

import argparse
import sys

from career_track_record import keywords


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
    return parser


def _write(stream, text):
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        stream.flush()
        buffer.write(text.encode("utf-8"))
        buffer.flush()
    else:
        stream.write(text)
        stream.flush()


def main(argv=None):
    args = _build_parser().parse_args(argv)
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
