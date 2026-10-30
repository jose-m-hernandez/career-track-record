# Command line: behaviour spec

Status: accepted.
Date: 2026-10-22.
Revision: 2. Adds `<cli> ab`, with its subcommands `freeze`, `run` and `score` and its fixed help text (sections 2, 4 and 5).

`<cli>` is the command name until it is settled. This release names it `track-record`.

## 1. Scope

The top-level command, and the help rule every command shares. Each command's own spec governs everything else: keywords (keyword-scan.md), barred (barred.md), tone (tone-and-tells.md), ab (reader-ab.md).

## 2. Running a command

`<cli> keywords`, `<cli> barred`, `<cli> tone` and `<cli> ab` run that command under its own spec. `ab` has three subcommands: `<cli> ab freeze PLAN`, `<cli> ab run PLAN [--live]` and `<cli> ab score PLAN`.

## 3. Usage errors

`<cli>` with no command, or with a command it does not know, exits `2`, writes nothing to standard output, and writes a usage message to standard error.

## 4. Help

`-h` and `--help` are accepted at every level: `<cli>`, `<cli> keywords`, each keywords mode, `<cli> barred`, `<cli> tone`, `<cli> ab` and each `ab` subcommand. Help goes to standard output, nothing goes to standard error, and the run exits `0`. Help reads no input file, list or rule file.

`<cli> --help` names the command in its usage line and lists the four commands, each with its one-line description:

- keywords: scan saved job postings for terms
- barred: report wording from your own barred list
- tone: flag hype, hedges and filler in your copy
- ab: compare two versions of your copy with test readers

If help cannot be written (standard output closed, or a write fails), the run stops, exits `2` and writes one line to standard error, `cannot run: cannot write output`, with no traceback. This is the same rule each command's spec states for its own output.

## 5. What this spec does not promise

The exact layout of the help and usage messages from `<cli>` and `<cli> keywords` is not promised. That includes section headings and line wrapping, which come from Python's argument parser and differ between Python versions. Only barred, tone and ab promise fixed help text. Barred and tone state theirs in their own specs. For `ab`, the help of `<cli> ab` and of each of its subcommands is fixed text, pinned by the command's tests. A missing or unknown subcommand, a missing PLAN, an extra argument or an unknown option exits `2` with one `cannot run: ...` line on standard error and nothing on standard output.
