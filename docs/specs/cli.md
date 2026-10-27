# Command line: behaviour spec

Status: accepted.
Date: 2026-10-22.
Revision: 1.

`<cli>` is the command name until it is settled. This release names it `track-record`.

## 1. Scope

The top-level command, and the help rule every command shares. Each command's own spec governs everything else: keywords (keyword-scan.md), barred (barred.md), tone (tone-and-tells.md).

## 2. Running a command

`<cli> keywords`, `<cli> barred` and `<cli> tone` run that command under its own spec.

## 3. Usage errors

`<cli>` with no command, or with a command it does not know, exits `2`, writes nothing to standard output, and writes a usage message to standard error.

## 4. Help

`-h` and `--help` are accepted at every level: `<cli>`, `<cli> keywords`, each keywords mode, `<cli> barred` and `<cli> tone`. Help goes to standard output, nothing goes to standard error, and the run exits `0`. Help reads no input file, list or rule file.

`<cli> --help` names the command in its usage line and lists the three commands, each with its one-line description:

- keywords: scan saved job postings for terms
- barred: report wording from your own barred list
- tone: flag hype, hedges and filler in your copy

If help cannot be written (standard output closed, or a write fails), the run stops, exits `2` and writes one line to standard error, `cannot run: cannot write output`, with no traceback. This is the same rule each command's spec states for its own output.

## 5. What this spec does not promise

The exact layout of the help and usage messages from `<cli>` and `<cli> keywords` is not promised. That includes section headings and line wrapping, which come from Python's argument parser and differ between Python versions. Only barred and tone promise fixed help text, in their own specs.
